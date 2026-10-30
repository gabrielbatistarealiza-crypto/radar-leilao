"""Fase 3 na API: pesquisa, detalhe, histórico e alertas com imóveis fora da lista."""
from datetime import datetime

from app.models.criterio_alerta import CriterioAlerta
from app.models.imovel import ImovelEvento


def buscar(http, **params):
    resposta = http.get("/imoveis/", params={"status_leilao": "todos", "modalidade": "", **params})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_pesquisa_esconde_imoveis_fora_da_lista(http, fabrica):
    fabrica.imovel(titulo="Na lista")
    fabrica.imovel(titulo="Saiu", na_lista=False, saiu_da_lista_em=datetime(2026, 10, 29))

    corpo = buscar(http)

    assert [i["titulo"] for i in corpo["items"]] == ["Na lista"] and corpo["total"] == 1
    assert corpo["items"][0]["na_lista"] is True


def test_detalhe_de_imovel_fora_da_lista_continua_a_abrir_com_o_aviso(http, fabrica):
    imovel = fabrica.imovel(titulo="Saiu", na_lista=False, saiu_da_lista_em=datetime(2026, 10, 29, 22))

    corpo = http.get(f"/imoveis/{imovel.id}").json()

    assert corpo["na_lista"] is False
    assert corpo["saiu_da_lista_em"].startswith("2026-10-29T22")


def test_historico_do_imovel_em_ordem(http, fabrica, sessao):
    imovel = fabrica.imovel()
    sessao.add_all([
        ImovelEvento(imovel_id=imovel.id, tipo=ImovelEvento.SAIU, momento=datetime(2026, 10, 30)),
        ImovelEvento(imovel_id=imovel.id, tipo=ImovelEvento.PRECO, momento=datetime(2026, 10, 1),
                     valor_anterior=150000.0, valor_novo=120000.0),
    ])
    sessao.commit()

    corpo = http.get(f"/imoveis/{imovel.id}/historico").json()

    assert [e["tipo"] for e in corpo] == [ImovelEvento.PRECO, ImovelEvento.SAIU]
    assert corpo[0]["valor_anterior"] == 150000.0 and corpo[0]["valor_novo"] == 120000.0
    assert http.get("/imoveis/99999/historico").status_code == 404


def test_worker_de_datas_nao_pede_imoveis_fora_da_lista(fabrica, sessao):
    from app.models.imovel import Imovel
    from app.services.caixa_datas_edital import filtro_pendentes

    url = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"
    sem_datas = dict(fonte="Caixa", data_primeiro_leilao=None, data_segundo_leilao=None)
    na_lista = fabrica.imovel(url=url.format(1), **sem_datas)
    fabrica.imovel(url=url.format(2), na_lista=False, **sem_datas)

    pendentes = [i for (i,) in sessao.query(Imovel.id).filter(filtro_pendentes())]

    assert pendentes == [na_lista.id]


def test_alertas_nao_mostram_imoveis_fora_da_lista(http, fabrica, sessao, cliente, autenticar):
    fabrica.imovel(titulo="Na lista", cidade="Campinas")
    fabrica.imovel(titulo="Saiu", cidade="Campinas", na_lista=False)
    sessao.add(CriterioAlerta(usuario_id=cliente.id, nome="Campinas", cidade="Campinas", ativo=True))
    sessao.commit()

    resposta = http.get("/alertas/correspondencias", headers=autenticar(cliente))

    assert resposta.status_code == 200, resposta.text
    titulos = {i["imovel"]["titulo"] if "imovel" in i else i.get("titulo") for i in resposta.json()}
    assert "Saiu" not in titulos and "Na lista" in titulos
