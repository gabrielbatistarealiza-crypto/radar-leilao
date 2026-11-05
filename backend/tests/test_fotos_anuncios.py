"""Fotos dos anúncios carregadas do aparelho (guardadas na base). Sem rede."""
import base64

from app.models.anuncio_imagem import AnuncioImagem
from app.routers import anuncios_imoveis

# Uma imagem mínima de cada tipo (só os primeiros bytes contam para o tipo).
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 200


def b64(dados):
    return base64.b64encode(dados).decode()


def anuncio_de(http, cabecalho):
    r = http.post("/anuncios-imoveis", headers=cabecalho, json={
        "titulo": "Casa", "valor_mercado": 100000, "valor_anunciado": 90000, "aceito_comissao": True})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_carregar_e_ver_a_foto(http, cliente, autenticar):
    cab = autenticar(cliente)
    aid = anuncio_de(http, cab)

    r = http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(JPEG)}, headers=cab)

    assert r.status_code == 201, r.text
    url = r.json()["url"]
    assert url.startswith("/anuncios-imoveis/fotos/") and len(url.rsplit("/", 1)[1]) == 32
    imagem = http.get(url)  # sem sessão, como uma <img>
    assert imagem.status_code == 200 and imagem.content == JPEG
    assert imagem.headers["content-type"] == "image/jpeg" and "immutable" in imagem.headers["cache-control"]
    # aparece na lista do dono
    assert http.get("/anuncios-imoveis/meus", headers=cab).json()[0]["fotos"][0]["url"] == url


def test_aceita_png_e_webp_e_data_url(http, cliente, autenticar):
    cab = autenticar(cliente)
    aid = anuncio_de(http, cab)
    for dados, tipo in ((PNG, "image/png"), (WEBP, "image/webp")):
        r = http.post(f"/anuncios-imoveis/{aid}/fotos/carregar",
                      json={"conteudo_base64": f"data:{tipo};base64,{b64(dados)}"}, headers=cab)
        assert r.status_code == 201, r.text
        assert http.get(r.json()["url"]).headers["content-type"] == tipo


def test_recusa_o_que_nao_e_imagem_e_ficheiros_grandes(http, cliente, autenticar, monkeypatch):
    cab = autenticar(cliente)
    aid = anuncio_de(http, cab)
    texto = http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(b"<html>ola</html>" * 5)}, headers=cab)
    assert texto.status_code == 400 and "JPG, PNG ou WEBP" in texto.json()["detail"]
    assert http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": "isto-nao-e-base64!!"},
                     headers=cab).status_code == 400
    monkeypatch.setattr(anuncios_imoveis, "MAX_BYTES_FOTO", 100)
    grande = http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(JPEG)}, headers=cab)
    assert grande.status_code == 400 and "grande" in grande.json()["detail"]


def test_maximo_de_fotos(http, cliente, autenticar, monkeypatch):
    monkeypatch.setattr(anuncios_imoveis, "MAX_FOTOS", 2)
    cab = autenticar(cliente)
    aid = anuncio_de(http, cab)
    for _ in range(2):
        assert http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(JPEG)}, headers=cab).status_code == 201
    r = http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(JPEG)}, headers=cab)
    assert r.status_code == 400 and "no máximo 2 fotos" in r.json()["detail"]


def test_so_o_dono_carrega_e_remove(http, sessao, cliente, outro_cliente, autenticar):
    cab = autenticar(cliente)
    aid = anuncio_de(http, cab)
    foto = http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(JPEG)}, headers=cab).json()
    intruso = autenticar(outro_cliente)
    assert http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(JPEG)}, headers=intruso).status_code == 403
    assert http.delete(f"/anuncios-imoveis/{aid}/fotos/{foto['id']}", headers=intruso).status_code == 403

    assert http.delete(f"/anuncios-imoveis/{aid}/fotos/{foto['id']}", headers=cab).status_code == 204
    sessao.expire_all()
    assert sessao.query(AnuncioImagem).count() == 0
    assert http.get(foto["url"]).status_code == 404


def test_foto_nova_num_anuncio_publicado_volta_a_analise(http, cliente, admin, autenticar):
    cab = autenticar(cliente)
    aid = anuncio_de(http, cab)
    http.post(f"/anuncios-imoveis/{aid}/aprovar", headers=autenticar(admin))
    http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(JPEG)}, headers=cab)
    assert http.get("/anuncios-imoveis/meus", headers=cab).json()[0]["status"] == "em_analise"


def test_chave_invalida_ou_desconhecida_da_404(http):
    assert http.get("/anuncios-imoveis/fotos/naoexiste").status_code == 404
    assert http.get("/anuncios-imoveis/fotos/" + "a" * 32).status_code == 404


def test_listas_nao_carregam_os_bytes(http, sessao, cliente, autenticar):
    from sqlalchemy import event

    cab = autenticar(cliente)
    aid = anuncio_de(http, cab)
    http.post(f"/anuncios-imoveis/{aid}/fotos/carregar", json={"conteudo_base64": b64(JPEG)}, headers=cab)
    comandos = []

    def guardar(conn, cursor, sql, *resto):
        comandos.append(sql)

    motor = sessao.get_bind()
    event.listen(motor, "before_cursor_execute", guardar)
    try:
        sessao.expire_all()
        http.get("/anuncios-imoveis/meus", headers=cab)
    finally:
        event.remove(motor, "before_cursor_execute", guardar)
    assert not any("anuncio_imagens.conteudo" in c for c in comandos)
