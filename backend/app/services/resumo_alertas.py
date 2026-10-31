"""Resumo diário dos alertas por e-mail (Brevo).

Uma vez por dia por utilizador, a partir de RADAR_RESUMO_HORA_UTC (padrão 11 =
08:00 em Brasília), junta as notificações ainda não enviadas dos últimos 7 dias
num só e-mail (até 10 imóveis). Notificações mais antigas não seguem por e-mail.
Quem desligar os e-mails (pela ligação do próprio e-mail ou no site) não recebe.
"""
import hashlib
import logging
import os
from datetime import datetime, timedelta
from html import escape

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.models.imovel import Imovel
from app.models.notificacao import Notificacao
from app.models.usuario import Usuario
from app.security.token import ALGORITHM, SECRET_KEY
from app.services import email as servico_email

logger = logging.getLogger(__name__)

MAX_IMOVEIS = 10
JANELA = timedelta(days=7)
FIM_DO_TOKEN = "desligar-alertas"
# Chave própria: um token desta ligação nunca vale como sessão (nem o contrário).
_CHAVE = hashlib.sha256(f"{SECRET_KEY}:{FIM_DO_TOKEN}".encode()).hexdigest()


def hora_do_resumo() -> int:
    try:
        return min(23, max(0, int(os.getenv("RADAR_RESUMO_HORA_UTC", "11"))))
    except ValueError:
        return 11


def token_desligar(usuario_id: int) -> str:
    return jwt.encode({"fim": FIM_DO_TOKEN, "u": usuario_id}, _CHAVE, algorithm=ALGORITHM)


def usuario_do_token_desligar(token: str) -> int | None:
    try:
        dados = jwt.decode(token, _CHAVE, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if dados.get("fim") != FIM_DO_TOKEN or not isinstance(dados.get("u"), int):
        return None
    return dados["u"]


def _site() -> str:
    return os.getenv("RADAR_SITE_URL", "http://localhost:5173").rstrip("/")


def _reais(valor) -> str:
    if valor is None:
        return "-"
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _linha(n, imovel):
    """(título, detalhe) de uma notificação, curto e sem repetir o texto do alerta."""
    if imovel is None:
        return n.titulo, n.mensagem
    titulo = imovel.titulo or "Imóvel"
    if imovel.estado and imovel.estado not in titulo:
        titulo = f"{titulo} - {imovel.estado}"
    partes = []
    if n.tipo == "prazo":
        partes.append(n.mensagem.split(": ", 1)[-1].rstrip("."))  # "primeiro leilão em 3 dia(s), em ..."
    if imovel.valor_lance:
        partes.append(f"lance mínimo {_reais(imovel.valor_lance)}")
        desconto = imovel.desconto_atual
        if desconto and desconto > 0:
            partes.append(f"{desconto:.0f}% abaixo da avaliação")
    return titulo, " · ".join(partes)


def _ordenar(notificacoes, imoveis):
    """Leilões a aproximar-se primeiro; depois os maiores descontos."""
    def chave(n):
        i = imoveis.get(n.imovel_id)
        desconto = (i.desconto_atual or 0) if i is not None else 0
        return (n.tipo != "prazo", -desconto, -n.id)
    return sorted(notificacoes, key=chave)


def montar_email(usuario, notificacoes, imoveis, total: int) -> tuple[str, str, str]:
    """(assunto, html, texto) do resumo."""
    site = _site()
    desligar = f"{site}/desligar-alertas?token={token_desligar(usuario.id)}"
    assunto = (f"Radar Leilão: {total} novidade nos seus alertas" if total == 1
               else f"Radar Leilão: {total} novidades nos seus alertas")
    partes_txt, partes_html = [], []
    for n in notificacoes:
        titulo, detalhe = _linha(n, imoveis.get(n.imovel_id))
        aviso = "Leilão a aproximar-se: " if n.tipo == "prazo" else ""
        partes_txt.append(f"- {aviso}{titulo}" + (f" · {detalhe}" if detalhe else ""))
        partes_html.append(
            f"<li>{escape(aviso)}<strong>{escape(titulo)}</strong>"
            + (f"<br><small>{escape(detalhe)}</small>" if detalhe else "") + "</li>"
        )
    resto = total - len(notificacoes)
    mais = f"E mais {resto} no site." if resto > 0 else ""
    texto = (f"Olá, {usuario.nome}.\n\nNovidades dos seus alertas no Radar Leilão:\n\n"
             + "\n".join(partes_txt) + (f"\n\n{mais}" if mais else "")
             + f"\n\nVer no site: {site}\n\nPara deixar de receber estes e-mails: {desligar}\n")
    html = (f"<p>Olá, {escape(usuario.nome)}.</p><p>Novidades dos seus alertas no Radar Leilão:</p>"
            f"<ul>{''.join(partes_html)}</ul>" + (f"<p>{escape(mais)}</p>" if mais else "")
            + f'<p><a href="{escape(site)}">Ver no site</a></p>'
            + f'<p style="color:#888;font-size:12px">Não quer receber estes e-mails? '
              f'<a href="{escape(desligar)}">Desligar os resumos</a>.</p>')
    return assunto, html, texto


def enviar_resumos(db: Session, agora: datetime | None = None) -> dict:
    """Envia os resumos devidos. Devolve contagens; nunca levanta por causa do envio."""
    agora = agora or datetime.utcnow()
    resultado = {"enviados": 0, "falhados": 0, "sem_novidades": 0}
    if agora.hour < hora_do_resumo():
        resultado["motivo"] = "ANTES_DA_HORA"
        return resultado
    if not servico_email.email_configurado():
        resultado["motivo"] = "EMAIL_NAO_CONFIGURADO"
        return resultado

    limite_antigo = agora - JANELA
    # Antigas e nunca enviadas: deixam de contar (não se manda um histórico inteiro).
    db.query(Notificacao).filter(
        Notificacao.enviada_por_email_em.is_(None), Notificacao.criada_em < limite_antigo,
    ).update({"enviada_por_email_em": agora}, synchronize_session=False)
    db.commit()

    inicio_do_dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    ids = [uid for (uid,) in db.query(Notificacao.usuario_id).filter(
        Notificacao.enviada_por_email_em.is_(None)).distinct().all()]
    for usuario in db.query(Usuario).filter(Usuario.id.in_(ids)).all() if ids else []:
        if not usuario.alertas_por_email:
            continue
        if usuario.ultimo_resumo_email_em and usuario.ultimo_resumo_email_em >= inicio_do_dia:
            continue  # já recebeu hoje
        pendentes = (db.query(Notificacao)
                     .filter(Notificacao.usuario_id == usuario.id, Notificacao.enviada_por_email_em.is_(None))
                     .all())
        if not pendentes:
            resultado["sem_novidades"] += 1
            continue
        imoveis = {i.id: i for i in db.query(Imovel).filter(Imovel.id.in_({n.imovel_id for n in pendentes})).all()}
        mostrar = _ordenar(pendentes, imoveis)[:MAX_IMOVEIS]
        assunto, html, texto = montar_email(usuario, mostrar, imoveis, len(pendentes))
        if servico_email.enviar_email(usuario.email, assunto, html, texto):
            for n in pendentes:
                n.enviada_por_email_em = agora
            usuario.ultimo_resumo_email_em = agora
            db.commit()
            resultado["enviados"] += 1
        else:
            db.rollback()
            resultado["falhados"] += 1
            logger.warning("Resumo de alertas não enviado ao utilizador %s.", usuario.id)
    return resultado
