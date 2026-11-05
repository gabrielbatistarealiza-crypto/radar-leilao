"""Fecho da rotina (editais aplicados sozinhos, registo da execução) e avisos por e-mail.
Sem rede: o Brevo é trocado por um falso e os PDFs são texto depois de "%PDF-"."""
import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.execucao_rotina import AvisoSistema, ExecucaoRotina
from app.models.imovel import Imovel
from app.services import avisos_rotina
from app.services import caixa_datas_edital as ce
from app.services import email as servico_email
from app.services.fecho_rotina import fechar_execucao

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
N1, N2 = "8787714663143", "8555533895378"
D1, D2 = date(2026, 12, 14), date(2026, 12, 17)


def pdf(numeros, d1=D1, d2=D2):
    texto = (f"1.1 – Data e Hora da Sessão do 1º Leilão: {d1:%d/%m/%Y} às 10:00h.\n"
             f"1.2 – Data e Hora da Sessão do 2º Leilão: {d2:%d/%m/%Y} às 10:00h.\n"
             "Anexo II – RELAÇÃO DE IMÓVEIS\n"
             + "\n".join(f"{n}  149.014,00  111.258,07  140.000,00  " for n in numeros))
    return b"%PDF-" + texto.encode()


@pytest.fixture(autouse=True)
def pdf_de_texto_e_hoje(monkeypatch):
    monkeypatch.setattr(ce, "ler_edital", lambda corpo: ce.interpretar_texto_edital(corpo[5:].decode()))
    monkeypatch.setattr(ce, "_hoje", lambda: date(2026, 11, 5))


@pytest.fixture()
def pasta(tmp_path):
    p = tmp_path / "Editais"
    p.mkdir()
    return p


def imovel(fabrica, numero, **campos):
    base = dict(fonte="Caixa", url=URL.format(numero), data_primeiro_leilao=None, data_segundo_leilao=None)
    return fabrica.imovel(**{**base, **campos})


# ------------------------------------------------------------------ fecho

def test_fecho_aplica_edital_coerente_e_regista(sessao, fabrica, pasta):
    a = imovel(fabrica, N1)
    (pasta / "EL00580226CPARE.PDF").write_bytes(pdf([N1]))
    sessao.add(AtualizacaoCaixa(iniciada_em=datetime(2026, 11, 5, 15, 1), status="CONCLUIDA",
                                estados_baixados=27, imoveis_atualizados=4600, imoveis_removidos=3))
    sessao.commit()

    e = fechar_execucao(sessao, codigo_saida=0, iniciada_em=datetime(2026, 11, 5, 15, 0), pasta_editais=pasta)

    r = json.loads(e.resumo)
    assert e.codigo_saida == 0 and r["significado"] == "concluída"
    assert [x["ficheiro"] for x in r["editais_aplicados"]] == ["EL00580226CPARE.PDF"]
    assert r["editais_com_problema"] == [] and r["lista"]["imoveis_atualizados"] == 4600
    sessao.expire_all()
    assert (a.data_primeiro_leilao, a.data_segundo_leilao) == (D1, D2)
    assert a.link_edital.endswith("/EL00580226CPARE.PDF") and a.valor_segundo_leilao == 111258.07
    assert r["ultimo_edital"] == "EL00580226CPARE"
    assert r["experimentar"][0].endswith("/EL00590226CPARE.PDF")


def test_fecho_nao_grava_edital_incoerente(sessao, fabrica, pasta):
    a = imovel(fabrica, N1, data_primeiro_leilao=date(2026, 12, 1), data_segundo_leilao=date(2026, 12, 7))
    (pasta / "EL00580226CPARE.PDF").write_bytes(pdf([N1]))

    r = json.loads(fechar_execucao(sessao, codigo_saida=0, pasta_editais=pasta).resumo)

    assert r["editais_aplicados"] == []
    assert r["editais_com_problema"][0]["motivo"] == "EDITAL_INCOERENTE"
    assert r["editais_com_problema"][0]["imovel_incoerente"] == a.id
    sessao.expire_all()
    assert a.data_primeiro_leilao == date(2026, 12, 1) and a.link_edital is None


def test_fecho_ignora_edital_ja_passado(sessao, fabrica, pasta):
    imovel(fabrica, N1)
    (pasta / "EL00400226CPARE.PDF").write_bytes(pdf([N1], d1=date(2026, 10, 1), d2=date(2026, 10, 5)))
    r = json.loads(fechar_execucao(sessao, codigo_saida=0, pasta_editais=pasta).resumo)
    assert r["editais_ignorados"][0]["motivo"] == "EDITAL_JA_PASSOU" and r["editais_aplicados"] == []


def test_fecho_sem_aplicar_e_codigos(sessao, fabrica, pasta):
    imovel(fabrica, N1)
    (pasta / "EL00580226CPARE.PDF").write_bytes(pdf([N1]))
    e = fechar_execucao(sessao, codigo_saida=3, pasta_editais=pasta, cauda_log="VPN ligada", aplicar_editais=False)
    r = json.loads(e.resumo)
    assert r["editais_aplicados"] == [] and "VPN" in r["significado"] and r["cauda_log"] == "VPN ligada"
    assert sessao.query(Imovel).filter(Imovel.link_edital.isnot(None)).count() == 0


# ------------------------------------------------------------------ avisos por e-mail

@pytest.fixture()
def correio(monkeypatch):
    enviados = []
    estado = SimpleNamespace(falhar=False)

    def enviar(para, assunto, html, texto):
        if estado.falhar:
            return False
        enviados.append(SimpleNamespace(para=para, assunto=assunto, texto=texto))
        return True

    monkeypatch.setattr(servico_email, "enviar_email", enviar)
    monkeypatch.setattr(servico_email, "email_configurado", lambda: True)
    monkeypatch.delenv("RADAR_ROTINA_DIAS_SEM_EXECUCAO", raising=False)
    return SimpleNamespace(enviados=enviados, estado=estado)


def execucao(sessao, codigo=0, quando=datetime(2026, 11, 5, 15, 30), **resumo):
    e = ExecucaoRotina(terminada_em=quando, codigo_saida=codigo, resumo=json.dumps({
        "significado": "concluída", "lista": {"status": "CONCLUIDA", "estados_baixados": 27,
                                               "imoveis_atualizados": 4600, "imoveis_removidos": 2},
        "editais_aplicados": [], "editais_com_problema": [], "pendentes_de_datas": 3,
        "ultimo_edital": "EL00570226CPARE",
        "experimentar": ["https://venda-imoveis.caixa.gov.br/editais/EL00580226CPARE.PDF"], **resumo}))
    sessao.add(e)
    sessao.commit()
    return e


def test_avisa_cada_execucao_aos_admins(sessao, admin, cliente, correio):
    e = execucao(sessao, editais_com_problema=[{"ficheiro": "EL0058.PDF", "motivo": "EDITAL_INCOERENTE",
                                                "imovel_incoerente": 14205}])

    assert avisos_rotina.avisar_execucoes(sessao) == 1

    assert [m.para for m in correio.enviados] == [admin.email]  # só administradores
    m = correio.enviados[0]
    assert "rotina da Caixa concluída" in m.assunto and "1 edital(is) para rever" in m.assunto
    assert "4600 imóveis atualizados" in m.texto and "EL0058.PDF" in m.texto and "Imóvel 14205" in m.texto
    assert "datas futuras de outro edital" in m.texto  # motivo em linguagem simples
    assert "EL00580226CPARE.PDF" in m.texto
    sessao.expire_all()
    assert e.avisado_em is not None
    assert avisos_rotina.avisar_execucoes(sessao) == 0  # não repete


def test_datas_dos_editais_aplicados_ficam_legiveis(sessao, admin, correio):
    execucao(sessao, editais_aplicados=[{"ficheiro": "EL00580226CPARE.PDF", "datas": ["2026-12-14", "2026-12-17"],
                                         "imoveis": 570, "valores": 570}])
    avisos_rotina.avisar_execucoes(sessao)
    assert "leilões em 14/12/2026 e 17/12/2026" in correio.enviados[0].texto


def test_falha_no_envio_tenta_depois(sessao, admin, correio):
    e = execucao(sessao, codigo=2, significado="parou")
    correio.estado.falhar = True
    assert avisos_rotina.avisar_execucoes(sessao) == 0
    sessao.expire_all()
    assert e.avisado_em is None
    correio.estado.falhar = False
    assert avisos_rotina.avisar_execucoes(sessao) == 1
    assert "rotina da Caixa parou" in correio.enviados[0].assunto


def test_sem_brevo_nao_faz_nada(sessao, admin, correio, monkeypatch):
    monkeypatch.setattr(servico_email, "email_configurado", lambda: False)
    execucao(sessao)
    assert avisos_rotina.avisar_execucoes(sessao) == 0 and correio.enviados == []


def test_rotina_parada_avisa_uma_vez_por_dia(sessao, admin, correio):
    execucao(sessao, quando=datetime(2026, 11, 1, 15, 30))
    sessao.query(ExecucaoRotina).update({"avisado_em": datetime(2026, 11, 1, 16)})
    sessao.commit()

    assert avisos_rotina.avisar_rotina_parada(sessao, agora=datetime(2026, 11, 4, 12)) is False  # 3 dias
    assert avisos_rotina.avisar_rotina_parada(sessao, agora=datetime(2026, 11, 5, 16)) is True   # 4 dias
    assert "não corre há 4 dias" in correio.enviados[0].assunto
    assert avisos_rotina.avisar_rotina_parada(sessao, agora=datetime(2026, 11, 5, 20)) is False  # mesmo dia
    assert avisos_rotina.avisar_rotina_parada(sessao, agora=datetime(2026, 11, 6, 17)) is True   # dia seguinte
    assert sessao.query(AvisoSistema).count() == 1


def test_rotina_parada_conta_tambem_as_importacoes_antigas(sessao, admin, correio):
    sessao.add(AtualizacaoCaixa(iniciada_em=datetime(2026, 11, 4, 15), status="CONCLUIDA"))
    sessao.commit()
    assert avisos_rotina.avisar_rotina_parada(sessao, agora=datetime(2026, 11, 5, 16)) is False


def test_sem_nenhuma_execucao_nao_avisa(sessao, admin, correio):
    assert avisos_rotina.avisar_rotina_parada(sessao, agora=datetime(2026, 11, 5)) is False


def test_dias_configuraveis(sessao, admin, correio, monkeypatch):
    monkeypatch.setenv("RADAR_ROTINA_DIAS_SEM_EXECUCAO", "2")
    execucao(sessao, quando=datetime(2026, 11, 3, 15))
    assert avisos_rotina.avisar_rotina_parada(sessao, agora=datetime(2026, 11, 5, 16)) is True
