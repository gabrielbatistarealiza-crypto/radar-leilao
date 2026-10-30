"""Recuperação de senha por e-mail (fase 4B).

POST /senha/esquecida  {email}          -> envia uma ligação (válida 1 hora), se a conta existir.
                                           A resposta é sempre a mesma, exista ou não a conta.
POST /senha/redefinir  {codigo, senha}  -> troca a senha; cada ligação só serve uma vez.

RADAR_SITE_URL (ex.: https://radar-leilao-web.onrender.com) dá o endereço da ligação.
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.recuperacao_senha import RecuperacaoSenha
from app.models.usuario import Usuario
from app.routers.login import LimiteTentativasLogin
from app.security.password import gerar_hash
from app.services import email as servico_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/senha", tags=["Senha"])

VALIDADE = timedelta(hours=1)
RESPOSTA_PEDIDO = {"mensagem": "Se o e-mail estiver registado, enviámos uma ligação para redefinir a senha."}

# Por e-mail: no máximo 3 pedidos por hora. Global: 30 por hora (trava envios em massa).
limite_por_email = LimiteTentativasLogin(maximo=3, janela=3600)
limite_global = LimiteTentativasLogin(maximo=30, janela=3600)


class PedidoRecuperacao(BaseModel):
    email: EmailStr


class NovaSenha(BaseModel):
    codigo: str = Field(min_length=20, max_length=200)
    senha: str = Field(min_length=8, max_length=128)


def _hash(codigo: str) -> str:
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def _site() -> str:
    return os.getenv("RADAR_SITE_URL", "http://localhost:5173").rstrip("/")


def _mensagem(nome: str, ligacao: str) -> tuple[str, str]:
    texto = (f"Olá, {nome}.\n\nPara escolher uma senha nova no Radar Leilão, abra esta ligação "
             f"(válida durante 1 hora):\n{ligacao}\n\nSe não foi você que pediu, ignore este e-mail: "
             "a sua senha continua a mesma.")
    html = (f"<p>Olá, {escape(nome)}.</p><p>Para escolher uma senha nova no Radar Leilão, "
            f'<a href="{escape(ligacao)}">clique aqui</a> (válido durante 1 hora).</p>'
            "<p>Se não foi você que pediu, ignore este e-mail: a sua senha continua a mesma.</p>")
    return html, texto


@router.post("/esquecida")
def pedir_recuperacao(dados: PedidoRecuperacao, db: Session = Depends(get_db)):
    chave = dados.email.strip().lower()
    if limite_global.segundos_de_bloqueio("todos") or limite_por_email.segundos_de_bloqueio(chave):
        return RESPOSTA_PEDIDO  # a mesma resposta: não revela nada nem envia mais
    limite_global.registar_falha("todos")
    limite_por_email.registar_falha(chave)

    usuario = db.query(Usuario).filter(func.lower(Usuario.email) == chave).first()
    if usuario is None:
        return RESPOSTA_PEDIDO

    agora = datetime.utcnow()
    codigo = secrets.token_urlsafe(32)
    db.add(RecuperacaoSenha(usuario_id=usuario.id, codigo_hash=_hash(codigo),
                            criado_em=agora, expira_em=agora + VALIDADE))
    db.commit()

    ligacao = f"{_site()}/redefinir-senha?codigo={codigo}"
    html, texto = _mensagem(usuario.nome, ligacao)
    if not servico_email.enviar_email(usuario.email, "Redefinir a senha do Radar Leilão", html, texto):
        logger.warning("Pedido de recuperação de senha criado mas o e-mail não foi enviado.")
    return RESPOSTA_PEDIDO


@router.post("/redefinir")
def redefinir(dados: NovaSenha, db: Session = Depends(get_db)):
    agora = datetime.utcnow()
    pedido = db.query(RecuperacaoSenha).filter(RecuperacaoSenha.codigo_hash == _hash(dados.codigo)).first()
    if pedido is None or pedido.usado_em is not None or pedido.expira_em < agora:
        raise HTTPException(status_code=400, detail="Ligação inválida ou expirada. Peça uma nova.")
    usuario = db.get(Usuario, pedido.usuario_id)
    if usuario is None:
        raise HTTPException(status_code=400, detail="Ligação inválida ou expirada. Peça uma nova.")

    usuario.senha = gerar_hash(dados.senha)
    # Esta ligação e todas as outras ainda por usar deste utilizador deixam de servir.
    db.query(RecuperacaoSenha).filter(
        RecuperacaoSenha.usuario_id == usuario.id, RecuperacaoSenha.usado_em.is_(None)
    ).update({"usado_em": agora}, synchronize_session=False)
    db.commit()
    return {"mensagem": "Senha alterada. Já pode entrar com a senha nova."}
