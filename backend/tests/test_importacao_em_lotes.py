"""Importação da lista da Caixa gravada em lotes (executar_scraper_caixa e
preparar_fila_fotos_caixa), sem rede.

Verifica que o resultado na base é o de sempre e que o número de consultas
não cresce com o número de imóveis (cada consulta à base remota é uma ida e
volta pela rede).
"""
import pytest
from sqlalchemy import event

from app.models.imovel import Imovel, ImovelFotoVerificacao, ImovelImagem
from app.schemas.imovel_scraper import ImovelScraper
from app.services import scraper_service
from app.services.scraper_service import ScraperService

URL = "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel={}"


def dto(numero, **extra):
    base = dict(titulo=f"Imóvel {numero}", url=URL.format(numero), cidade="Campinas",
                estado="SP", valor_avaliacao=200000.0, valor_leilao=100000.0, fonte="Caixa")
    base.update(extra)
    return ImovelScraper(**base)


class ListaQueFalha(list):
    """Quebra quando o serviço percorre as fotos: simula um erro ao gravar um imóvel."""

    def __bool__(self):
        return True

    def __iter__(self):
        raise RuntimeError("falha simulada ao salvar")


@pytest.fixture()
def contador(sessao):
    """Consultas feitas, menos os INSERT: o SQLite dos testes insere linha a linha,
    o PostgreSQL agrupa-os (medido na cópia), por isso só os outros são contados."""
    consultas = []

    def contar(conn, cursor, sql, *args, **kwargs):
        if not sql.lstrip().upper().startswith("INSERT"):
            consultas.append(sql)

    motor = sessao.get_bind()
    event.listen(motor, "before_cursor_execute", contar)
    yield consultas
    event.remove(motor, "before_cursor_execute", contar)


@pytest.fixture()
def importar(monkeypatch, sessao):
    def _importar(dtos):
        class ScraperFalso:
            def executar(self):
                return list(dtos)

        monkeypatch.setattr(scraper_service, "CaixaScraper", ScraperFalso)
        servico = ScraperService(sessao)
        return servico, servico.executar_scraper_caixa()

    return _importar


def por_numero(sessao, numero):
    return sessao.query(Imovel).filter(Imovel.url == URL.format(numero)).one()


def test_numero_de_consultas_nao_cresce_com_os_imoveis(importar, sessao, fabrica, contador):
    for n in range(0, 300, 2):  # metade já existe
        fabrica.imovel(url=URL.format(n), fonte="Caixa", valor_leilao=1.0)
    contador.clear()

    _, imoveis = importar([dto(n) for n in range(300)])

    assert len(imoveis) == 300
    # 2 lotes de 200: 1 SELECT e no máximo um UPDATE agrupado por lote
    # (antes: 2 consultas por imóvel, ou seja 600).
    assert len(contador) <= 4, contador
    sessao.expire_all()
    assert sessao.query(Imovel).count() == 300
    assert por_numero(sessao, 0).valor_leilao == pytest.approx(100000.0)


def test_imoveis_devolvidos_nao_fazem_consultas_ao_ler(importar, contador):
    _, imoveis = importar([dto(1), dto(2)])
    contador.clear()

    assert [i.titulo for i in imoveis] == ["Imóvel 1", "Imóvel 2"]
    assert all(i.id for i in imoveis)
    assert contador == []


def test_restaura_expire_on_commit(importar, sessao):
    importar([dto(1)])
    assert sessao.expire_on_commit is True


def test_imovel_com_erro_nao_impede_os_outros_do_mesmo_lote(importar, sessao, monkeypatch):
    monkeypatch.setattr(ScraperService, "TAMANHO_LOTE_IMPORTACAO", 3)
    quebrado = ImovelScraper.model_construct(
        titulo="Vai falhar", url=URL.format(5), fonte="Caixa", imagens=ListaQueFalha()
    )

    servico, imoveis = importar([dto(1), dto(2), quebrado, dto(3), dto(4)])

    sessao.expire_all()
    numeros = sorted(int(i.url.rsplit("=", 1)[1]) for i in sessao.query(Imovel).all())
    assert numeros == [1, 2, 3, 4]
    assert len(imoveis) == 4
    # Continua contado como "visto": não pode ser tratado como removido da lista.
    assert URL.format(5) in servico.urls_vistas


def test_url_repetida_na_lista_cria_um_e_fica_com_os_ultimos_valores(importar, sessao):
    importar([dto(1, valor_leilao=10.0, quartos=2), dto(1, valor_leilao=20.0)])

    sessao.expire_all()
    imovel = por_numero(sessao, 1)
    assert sessao.query(Imovel).count() == 1
    assert imovel.valor_leilao == pytest.approx(20.0)
    assert imovel.quartos == 2  # valor ausente no segundo não apaga


def test_fotos_novas_e_existentes_sem_duplicar(importar, sessao, fabrica):
    existente = fabrica.imovel(url=URL.format(1), fonte="Caixa")
    fabrica.foto(existente, "http://x/a.jpg")

    importar([
        dto(1, imagens=["http://x/a.jpg", "http://x/b.jpg"]),
        dto(2, imagem="http://x/capa.jpg", imagens=["http://x/c.jpg", "http://x/c.jpg"]),
    ])

    sessao.expire_all()
    fotos = {(f.imovel_id, f.url, f.ordem) for f in sessao.query(ImovelImagem).all()}
    novo = por_numero(sessao, 2).id
    assert fotos == {
        (existente.id, "http://x/a.jpg", 0), (existente.id, "http://x/b.jpg", 1),
        (novo, "http://x/capa.jpg", 0), (novo, "http://x/c.jpg", 1),
    }
    assert por_numero(sessao, 2).imagens == ["http://x/capa.jpg", "http://x/c.jpg"]


# ------------------------------------------------------------ fila de fotos

def test_fila_de_fotos_com_consultas_constantes_e_mesmos_estados(sessao, fabrica, contador):
    com_foto = fabrica.imovel(fonte="Caixa")
    fabrica.foto(com_foto, "http://x/a.jpg")
    sem_verificacao = fabrica.imovel(fonte="Caixa")
    com_erro = fabrica.imovel(fonte="Caixa")
    sem_fotos = fabrica.imovel(fonte="Caixa")
    outros = [fabrica.imovel(fonte="Caixa") for _ in range(30)]
    for imovel, resultado in [(com_erro, "ERRO"), (sem_fotos, "SEM_FOTOS"), (com_foto, "PENDENTE")]:
        sessao.add(ImovelFotoVerificacao(imovel_id=imovel.id, resultado=resultado))
    sessao.commit()
    contador.clear()

    lista = [com_foto, sem_verificacao, com_erro, sem_fotos, *outros, sem_verificacao]
    r = ScraperService(sessao).preparar_fila_fotos_caixa(lista)

    # 2 SELECTs + UPDATE agrupado, independentemente dos 34 imóveis (antes: 70+).
    assert len(contador) <= 3, contador
    # 1 sem verificação + 1 com ERRO + 30 novos; o repetido já está PENDENTE e não conta 2x.
    assert r == {"pendentes": 32, "com_fotos": 1, "sem_fotos": 1}
    sessao.expire_all()
    estados = {v.imovel_id: v.resultado for v in sessao.query(ImovelFotoVerificacao).all()}
    assert estados[com_foto.id] == "COM_FOTOS"
    assert estados[sem_verificacao.id] == "PENDENTE"
    assert estados[com_erro.id] == "PENDENTE"
    assert estados[sem_fotos.id] == "SEM_FOTOS"
    assert len(estados) == 34  # o repetido não cria segunda verificação
