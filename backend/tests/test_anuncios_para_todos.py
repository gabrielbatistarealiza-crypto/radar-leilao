"""Anúncios para todos: qualquer conta publica, sem mínimo de desconto, comissão de 6%
aceite ao publicar e aprovação por um administrador. Sem rede."""
from app.models.anuncio_imovel import AnuncioImovel
from app.models.oportunidade import Oportunidade

ANUNCIO = {
    "titulo": "Casa em Campinas",
    "cidade": "Campinas",
    "estado": "sp",
    "valor_mercado": 300000,
    "valor_anunciado": 285000,  # 5%: antes era recusado (mínimo 20%)
    "aceito_comissao": True,
}


def publicar(http, cabecalho, **mudar):
    return http.post("/anuncios-imoveis", json={**ANUNCIO, **mudar}, headers=cabecalho)


def test_cliente_publica_e_fica_em_analise(http, sessao, cliente, autenticar):
    r = publicar(http, autenticar(cliente))

    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["status"] == "em_analise" and corpo["usuario_id"] == cliente.id
    assert corpo["corretor_id"] is None and corpo["desconto"] == 5.0 and corpo["estado"] == "SP"
    assert corpo["comissao_percentual"] == 6.0 and corpo["comissao_aceite_em"]
    # Ainda não é público.
    assert http.get("/anuncios-imoveis/publicados").json() == []
    assert http.get(f"/anuncios-imoveis/{corpo['id']}").status_code == 404


def test_sem_aceitar_a_comissao_nao_publica(http, cliente, autenticar):
    r = publicar(http, autenticar(cliente), aceito_comissao=False)
    assert r.status_code == 400 and "6%" in r.json()["detail"]


def test_sem_sessao_nao_publica(http):
    assert http.post("/anuncios-imoveis", json=ANUNCIO).status_code == 401


def test_valores_invalidos_continuam_recusados(http, cliente, autenticar):
    cab = autenticar(cliente)
    assert publicar(http, cab, valor_anunciado=400000).status_code == 400  # acima do mercado
    assert publicar(http, cab, valor_mercado=0).status_code == 400


def test_corretor_publica_com_o_seu_perfil(http, fabrica, corretor, autenticar):
    perfil = fabrica.perfil_corretor(corretor)
    corpo = publicar(http, autenticar(corretor)).json()
    assert corpo["corretor_id"] == perfil.id and corpo["status"] == "em_analise"


def test_admin_aprova_e_passa_a_ser_publico(http, cliente, admin, autenticar):
    anuncio_id = publicar(http, autenticar(cliente)).json()["id"]

    fila = http.get("/anuncios-imoveis/moderacao", headers=autenticar(admin)).json()
    assert [a["id"] for a in fila] == [anuncio_id]
    assert fila[0]["dono"]["email"] == cliente.email and fila[0]["comissao_percentual"] == 6.0

    r = http.post(f"/anuncios-imoveis/{anuncio_id}/aprovar", headers=autenticar(admin))
    assert r.status_code == 200 and r.json()["status"] == "publicado"
    publicos = http.get("/anuncios-imoveis/publicados").json()
    assert [a["id"] for a in publicos] == [anuncio_id]
    assert "usuario_id" not in publicos[0] and "comissao_aceite_em" not in publicos[0]


def test_admin_rejeita_com_motivo_e_o_dono_ve(http, cliente, admin, autenticar):
    anuncio_id = publicar(http, autenticar(cliente)).json()["id"]
    r = http.post(f"/anuncios-imoveis/{anuncio_id}/rejeitar", json={"motivo": "Faltam fotos"},
                  headers=autenticar(admin))
    assert r.status_code == 200 and r.json()["status"] == "rejeitado"
    meus = http.get("/anuncios-imoveis/meus", headers=autenticar(cliente)).json()
    assert meus[0]["status"] == "rejeitado" and meus[0]["motivo_rejeicao"] == "Faltam fotos"


def test_so_admin_modera(http, cliente, autenticar):
    anuncio_id = publicar(http, autenticar(cliente)).json()["id"]
    assert http.get("/anuncios-imoveis/moderacao", headers=autenticar(cliente)).status_code == 403
    assert http.post(f"/anuncios-imoveis/{anuncio_id}/aprovar", headers=autenticar(cliente)).status_code == 403


def test_anuncio_do_admin_fica_publicado_logo(http, admin, autenticar):
    assert publicar(http, autenticar(admin)).json()["status"] == "publicado"


def test_outro_utilizador_nao_edita_nem_apaga(http, cliente, outro_cliente, autenticar):
    anuncio_id = publicar(http, autenticar(cliente)).json()["id"]
    cab = autenticar(outro_cliente)
    assert http.put(f"/anuncios-imoveis/{anuncio_id}", json=ANUNCIO, headers=cab).status_code == 403
    assert http.delete(f"/anuncios-imoveis/{anuncio_id}", headers=cab).status_code == 403
    assert http.post(f"/anuncios-imoveis/{anuncio_id}/fotos", json={"url": "https://x/y.jpg"},
                     headers=cab).status_code == 403


def test_dono_apaga_o_seu_anuncio(http, sessao, cliente, autenticar):
    anuncio_id = publicar(http, autenticar(cliente)).json()["id"]
    assert http.delete(f"/anuncios-imoveis/{anuncio_id}", headers=autenticar(cliente)).status_code == 204
    sessao.expire_all()
    assert sessao.get(AnuncioImovel, anuncio_id) is None


def test_interesse_em_anuncio_sem_corretor_fica_sem_corretor(http, sessao, cliente, outro_cliente, admin, autenticar):
    anuncio_id = publicar(http, autenticar(cliente)).json()["id"]
    http.post(f"/anuncios-imoveis/{anuncio_id}/aprovar", headers=autenticar(admin))

    r = http.post(f"/oportunidades/anuncio/{anuncio_id}/interesse", headers=autenticar(outro_cliente))

    assert r.status_code == 201, r.text
    sessao.expire_all()
    op = sessao.query(Oportunidade).one()
    assert op.cliente_id == outro_cliente.id and op.corretor_id is None and op.anuncio_id == anuncio_id
    # Quem publicou não pode demonstrar interesse no próprio anúncio.
    proprio = http.post(f"/oportunidades/anuncio/{anuncio_id}/interesse", headers=autenticar(cliente))
    assert proprio.status_code == 400


def test_apagar_a_conta_apaga_os_anuncios_da_pessoa(http, sessao, cliente, autenticar):
    publicar(http, autenticar(cliente))
    r = http.post("/usuarios/me/apagar", json={"senha": "Senha#12345"}, headers=autenticar(cliente))
    assert r.status_code == 200
    sessao.expire_all()
    assert sessao.query(AnuncioImovel).count() == 0
