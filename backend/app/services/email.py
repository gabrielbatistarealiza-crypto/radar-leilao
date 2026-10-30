"""Envio de e-mails transacionais pelo Brevo (API HTTP).

Configuração (variáveis de ambiente, só no Render / no terminal, nunca no Git):
  BREVO_API_KEY          chave da API do Brevo
  RADAR_EMAIL_REMETENTE  e-mail remetente confirmado no Brevo
  RADAR_EMAIL_NOME       nome do remetente (padrão: "Radar Leilão")
Sem chave ou sem remetente, nada é enviado: fica um aviso no log e devolve False.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

URL_BREVO = "https://api.brevo.com/v3/smtp/email"


def email_configurado() -> bool:
    return bool(os.getenv("BREVO_API_KEY", "").strip() and os.getenv("RADAR_EMAIL_REMETENTE", "").strip())


def enviar_email(para: str, assunto: str, html: str, texto: str, enviar=None) -> bool:
    """Envia um e-mail. `enviar` substitui o pedido HTTP (testes). Nunca levanta exceções."""
    if not email_configurado():
        logger.warning("E-mail não enviado: BREVO_API_KEY ou RADAR_EMAIL_REMETENTE em falta.")
        return False
    corpo = {
        "sender": {"email": os.environ["RADAR_EMAIL_REMETENTE"].strip(),
                   "name": os.getenv("RADAR_EMAIL_NOME", "Radar Leilão")},
        "to": [{"email": para}],
        "subject": assunto,
        "htmlContent": html,
        "textContent": texto,
    }
    cabecalhos = {"api-key": os.environ["BREVO_API_KEY"].strip(), "accept": "application/json",
                  "content-type": "application/json"}
    try:
        resposta = (enviar or requests.post)(URL_BREVO, json=corpo, headers=cabecalhos, timeout=15)
    except Exception as erro:  # rede, timeout...
        logger.error("Falha ao enviar e-mail pelo Brevo: %s", type(erro).__name__)
        return False
    if resposta.status_code >= 300:
        logger.error("Brevo recusou o e-mail: HTTP %s", resposta.status_code)
        return False
    return True
