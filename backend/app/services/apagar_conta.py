"""Apagar uma conta e os dados pessoais ligados a ela (LGPD, direito à eliminação).

Usado pelo próprio utilizador (POST /usuarios/me/apagar) e pelo administrador.
A ordem importa: várias tabelas apontam para usuarios sem ON DELETE.

- Oportunidades em que a pessoa é CLIENTE: apagadas, com negociações, operações,
  simulações e atividades.
- Oportunidades em que é CORRETOR: ficam, mas voltam a "sem corretor" (o cliente
  não perde o seu histórico).
- Perfil de corretor e os seus anúncios (com fotos): apagados; oportunidades que
  apontavam para esses anúncios ficam sem anúncio.
- Pedidos de corretor, alertas, notificações e códigos de recuperação: apagados.
- Onde a pessoa só aparece como autora (atividades e simulações de outras
  oportunidades, decisões de pedidos): fica sem autor.
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.anuncio_imagem import AnuncioImagem
from app.models.anuncio_imovel import AnuncioImovel
from app.models.atividade_oportunidade import AtividadeOportunidade
from app.models.corretor import Corretor
from app.models.criterio_alerta import CriterioAlerta
from app.models.negociacao import Negociacao
from app.models.notificacao import Notificacao
from app.models.operacao import Operacao
from app.models.oportunidade import Oportunidade
from app.models.pedido_corretor import PedidoCorretor
from app.models.recuperacao_senha import RecuperacaoSenha
from app.models.simulacao_rentabilidade import SimulacaoRentabilidade
from app.models.usuario import Usuario


class UltimoAdministrador(Exception):
    """A conta é a do último administrador: o sistema ficaria sem nenhum."""


def _apagar(db: Session, modelo, *condicoes) -> int:
    return db.query(modelo).filter(*condicoes).delete(synchronize_session=False)


def apagar_conta(db: Session, usuario: Usuario) -> dict:
    """Apaga a conta e o que lhe pertence. Faz commit; devolve contagens."""
    if usuario.tipo == "admin" and db.query(Usuario).filter(Usuario.tipo == "admin").count() <= 1:
        raise UltimoAdministrador()

    uid = usuario.id
    resultado = {}

    # Oportunidades da pessoa como cliente, e tudo o que depende delas.
    ids_cliente = [i for (i,) in db.query(Oportunidade.id).filter(Oportunidade.cliente_id == uid).all()]
    if ids_cliente:
        for modelo in (Negociacao, Operacao, SimulacaoRentabilidade, AtividadeOportunidade):
            _apagar(db, modelo, modelo.oportunidade_id.in_(ids_cliente))
        resultado["oportunidades_apagadas"] = _apagar(db, Oportunidade, Oportunidade.id.in_(ids_cliente))

    # Como corretor: as oportunidades dos clientes ficam, sem corretor.
    resultado["oportunidades_sem_corretor"] = db.query(Oportunidade).filter(
        Oportunidade.corretor_id == uid).update({"corretor_id": None}, synchronize_session=False)

    # Anúncios da pessoa (qualquer conta pode publicar) e perfil de corretor.
    ids_perfil = [i for (i,) in db.query(Corretor.id).filter(Corretor.usuario_id == uid).all()]
    dono = AnuncioImovel.usuario_id == uid
    filtro = or_(dono, AnuncioImovel.corretor_id.in_(ids_perfil)) if ids_perfil else dono
    ids_anuncios = [i for (i,) in db.query(AnuncioImovel.id).filter(filtro).all()]
    if ids_anuncios:
        db.query(Oportunidade).filter(Oportunidade.anuncio_id.in_(ids_anuncios)).update(
            {"anuncio_id": None}, synchronize_session=False)
        _apagar(db, AnuncioImagem, AnuncioImagem.anuncio_id.in_(ids_anuncios))
        resultado["anuncios_apagados"] = _apagar(db, AnuncioImovel, AnuncioImovel.id.in_(ids_anuncios))
    if ids_perfil:
        _apagar(db, Corretor, Corretor.id.in_(ids_perfil))

    # Onde a pessoa só é autora: fica sem autor.
    db.query(AtividadeOportunidade).filter(AtividadeOportunidade.criado_por_id == uid).update(
        {"criado_por_id": None}, synchronize_session=False)
    db.query(SimulacaoRentabilidade).filter(SimulacaoRentabilidade.criado_por_id == uid).update(
        {"criado_por_id": None}, synchronize_session=False)
    db.query(PedidoCorretor).filter(PedidoCorretor.decidido_por == uid).update(
        {"decidido_por": None}, synchronize_session=False)

    for modelo in (PedidoCorretor, CriterioAlerta, Notificacao, RecuperacaoSenha):
        _apagar(db, modelo, modelo.usuario_id == uid)

    _apagar(db, Usuario, Usuario.id == uid)
    db.commit()
    return resultado
