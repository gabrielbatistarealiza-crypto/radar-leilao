"""Apagar a própria conta (LGPD) e a exclusão pelo administrador. Sem rede."""
from app.models.anuncio_imovel import AnuncioImovel
from app.models.corretor import Corretor
from app.models.criterio_alerta import CriterioAlerta
from app.models.negociacao import Negociacao
from app.models.notificacao import Notificacao
from app.models.oportunidade import Oportunidade
from app.models.pedido_corretor import PedidoCorretor
from app.models.usuario import Usuario

SENHA = "Senha#12345"  # a do conftest


def apagar(http, cabecalho, senha=SENHA):
    return http.post("/usuarios/me/apagar", json={"senha": senha}, headers=cabecalho)


def test_cliente_apaga_a_conta_e_os_seus_dados(http, sessao, fabrica, cliente, corretor, autenticar):
    imovel = fabrica.imovel()
    op = fabrica.oportunidade(cliente, imovel=imovel, corretor=corretor)
    fabrica.negociacao(op)
    sessao.add(CriterioAlerta(usuario_id=cliente.id, nome="SP"))
    sessao.add(Notificacao(usuario_id=cliente.id, imovel_id=imovel.id, evento="e", tipo="oportunidade",
                           titulo="t", mensagem="m"))
    sessao.add(PedidoCorretor(usuario_id=cliente.id, creci="CRECI-SP 1"))
    sessao.commit()
    cabecalho, uid = autenticar(cliente), cliente.id

    r = apagar(http, cabecalho)

    assert r.status_code == 200, r.text
    sessao.expire_all()
    assert sessao.get(Usuario, uid) is None
    for modelo in (Oportunidade, Negociacao, CriterioAlerta, Notificacao, PedidoCorretor):
        assert sessao.query(modelo).count() == 0, modelo.__name__
    assert sessao.get(Usuario, corretor.id) is not None  # o corretor continua
    assert http.get("/usuarios/me", headers=cabecalho).status_code == 401


def test_senha_errada_nao_apaga(http, sessao, cliente, autenticar):
    assert apagar(http, autenticar(cliente), senha="errada").status_code == 403
    sessao.expire_all()
    assert sessao.get(Usuario, cliente.id) is not None


def test_sem_sessao_nao_apaga(http):
    assert http.post("/usuarios/me/apagar", json={"senha": SENHA}).status_code == 401


def test_corretor_apaga_e_as_oportunidades_dos_clientes_ficam(http, sessao, fabrica, cliente, corretor, autenticar):
    perfil = fabrica.perfil_corretor(corretor)
    anuncio = fabrica.anuncio(perfil)
    op = fabrica.oportunidade(cliente, imovel=fabrica.imovel(), corretor=corretor, anuncio_id=anuncio.id)
    op_id = op.id

    assert apagar(http, autenticar(corretor)).status_code == 200

    sessao.expire_all()
    restante = sessao.get(Oportunidade, op_id)
    assert restante is not None and restante.corretor_id is None and restante.anuncio_id is None
    assert sessao.query(Corretor).count() == 0 and sessao.query(AnuncioImovel).count() == 0


def test_ultimo_administrador_nao_pode_apagar_a_conta(http, sessao, admin, autenticar):
    r = apagar(http, autenticar(admin))
    assert r.status_code == 400 and "último administrador" in r.json()["detail"]
    sessao.expire_all()
    assert sessao.get(Usuario, admin.id) is not None


def test_admin_apaga_com_outro_admin_e_decisoes_ficam_sem_autor(http, sessao, admin, cliente, autenticar):
    from tests.conftest import criar_usuario

    criar_usuario(sessao, "outro.admin@teste.com", "admin")
    pedido = PedidoCorretor(usuario_id=cliente.id, creci="CRECI-SP 2", status="REJEITADO", decidido_por=admin.id)
    sessao.add(pedido)
    sessao.commit()

    assert apagar(http, autenticar(admin)).status_code == 200

    sessao.expire_all()
    assert sessao.get(PedidoCorretor, pedido.id).decidido_por is None


def test_admin_exclui_cliente_com_oportunidades(http, sessao, fabrica, admin, cliente, autenticar):
    # Antes era um db.delete simples, que falhava com oportunidades ligadas.
    fabrica.negociacao(fabrica.oportunidade(cliente, imovel=fabrica.imovel()))
    uid = cliente.id

    r = http.delete(f"/admin/usuarios/{uid}", headers=autenticar(admin))

    assert r.status_code == 200, r.text
    sessao.expire_all()
    assert sessao.get(Usuario, uid) is None and sessao.query(Oportunidade).count() == 0
