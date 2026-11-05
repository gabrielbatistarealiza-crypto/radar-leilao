"""Avisos aos administradores sobre a rotina da Caixa (corre na API, não contacta a Caixa).

- Depois de cada execução registada pela tarefa local (execucoes_rotina): um e-mail com
  o que aconteceu (listas, editais aplicados ou por rever, próximo edital a experimentar).
- Se passarem RADAR_ROTINA_DIAS_SEM_EXECUCAO dias (padrão 4) sem nenhuma execução: um
  aviso, no máximo um por dia (o computador pode estar desligado ou a tarefa parada).
"""
import json
import logging
import os
from datetime import datetime, timedelta
from html import escape

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.execucao_rotina import AvisoSistema, ExecucaoRotina
from app.models.usuario import Usuario
from app.services import email as servico_email

logger = logging.getLogger(__name__)

AVISO_ROTINA_PARADA = "ROTINA_PARADA"

# Motivos dos editais não aplicados, em linguagem simples (o código fica entre parênteses).
MOTIVOS = {
    "EDITAL_INCOERENTE": "há imóveis com datas futuras de outro edital; reveja e aplique à mão "
                         "com --aplicar-edital ... --saltar-incoerentes",
    "NENHUM_IMOVEL_DA_BASE_NO_EDITAL": "nenhum imóvel deste edital está na base (a lista ainda não os "
                                       "trouxe?); volta a tentar na próxima execução",
    "EDITAL_NAO_INTERPRETAVEL": "não foi possível ler as datas e os imóveis do PDF (é mesmo um edital?)",
    "NOME_SEM_NUMERO_DO_EDITAL": "o nome do ficheiro tem de começar pelo número do edital (EL....PDF)",
    "EDITAL_JA_PASSOU": "as datas dos leilões já passaram",
    "IMOVEL_FORA_DO_EDITAL": "o edital não corresponde aos imóveis indicados",
}


def _motivo(codigo) -> str:
    return f"{MOTIVOS.get(codigo, 'motivo desconhecido')} ({codigo})"


def _datas(lista) -> str:
    """['2026-11-23', '2026-11-27'] -> '23/11/2026 e 27/11/2026'."""
    bonitas = []
    for valor in lista or []:
        try:
            bonitas.append(datetime.fromisoformat(str(valor)).strftime("%d/%m/%Y"))
        except ValueError:
            bonitas.append(str(valor))
    return " e ".join(bonitas) or "sem datas"


def dias_sem_execucao() -> int:
    try:
        return max(1, int(os.getenv("RADAR_ROTINA_DIAS_SEM_EXECUCAO", "4")))
    except ValueError:
        return 4


def _admins(db: Session) -> list[Usuario]:
    return db.query(Usuario).filter(Usuario.tipo == "admin").all()


def _enviar_a_todos(admins, assunto: str, linhas: list[str]) -> bool:
    texto = "\n".join(linhas)
    html = "".join(f"<p>{escape(l)}</p>" if l else "" for l in linhas)
    enviados = [servico_email.enviar_email(a.email, assunto, html, texto) for a in admins]
    return any(enviados)


def _linhas_execucao(e: ExecucaoRotina) -> tuple[str, list[str]]:
    r = json.loads(e.resumo or "{}")
    codigo = e.codigo_saida
    estado = "concluída" if codigo == 0 else ("parou" if codigo == 2 else "não correu" if codigo in (3, 4, 5) else "erro")
    problemas = r.get("editais_com_problema") or []
    assunto = f"Radar Leilão: rotina da Caixa {estado}"
    if problemas:
        assunto += f" ({len(problemas)} edital(is) para rever)"
    linhas = [f"Execução de {e.terminada_em:%d/%m/%Y %H:%M} UTC: {r.get('significado', estado)}.", ""]
    lista = r.get("lista")
    if lista:
        linhas.append(f"Listas: {lista.get('estados_baixados', 0)}/27 estados, {lista.get('imoveis_atualizados', 0)} "
                      f"imóveis atualizados, {lista.get('imoveis_removidos', 0)} saíram da lista "
                      f"(estado {lista.get('status')}).")
        if lista.get("erro"):
            linhas.append(f"Erro na importação: {lista['erro']}")
    elif codigo in (0, 2):
        linhas.append("Listas: nenhuma importação registada nesta execução.")
    for ed in r.get("editais_aplicados") or []:
        linhas.append(f"Edital aplicado: {ed['ficheiro']} — {ed.get('imoveis', 0)} imóveis, "
                      f"leilões em {_datas(ed.get('datas'))}, {ed.get('valores', 0)} com valores de lance.")
    for ed in problemas:
        extra = f" Imóvel {ed['imovel_incoerente']}." if ed.get("imovel_incoerente") else ""
        linhas.append(f"Edital NÃO aplicado: {ed['ficheiro']} — {_motivo(ed['motivo'])}.{extra}")
    for ed in r.get("editais_ignorados") or []:
        linhas.append(f"Edital ignorado: {ed['ficheiro']} — {_motivo(ed['motivo'])}; pode tirá-lo da pasta.")
    linhas.append(f"Imóveis à espera de datas (edital): {r.get('pendentes_de_datas', 0)}.")
    if r.get("ultimo_edital"):
        linhas.append(f"Último edital aplicado: {r['ultimo_edital']}.")
    if r.get("experimentar"):
        linhas.append("Próximos editais a experimentar no browser (404 = ainda não saiu); "
                      "se abrir, guarde o PDF na pasta Editais:")
        linhas.extend(f"  {link}" for link in r["experimentar"])
    if r.get("cauda_log"):
        linhas += ["", "Fim do registo da execução:", r["cauda_log"]]
    return assunto, linhas


def avisar_execucoes(db: Session, agora: datetime | None = None) -> int:
    """Envia o e-mail de cada execução ainda não avisada. Devolve quantas foram avisadas."""
    if not servico_email.email_configurado():
        return 0
    agora = agora or datetime.utcnow()
    pendentes = (db.query(ExecucaoRotina).filter(ExecucaoRotina.avisado_em.is_(None))
                 .order_by(ExecucaoRotina.terminada_em).all())
    admins = _admins(db)
    avisadas = 0
    for execucao in pendentes:
        if not admins:
            execucao.avisado_em = agora  # sem destinatários: não fica a acumular
            continue
        assunto, linhas = _linhas_execucao(execucao)
        if _enviar_a_todos(admins, assunto, linhas):
            execucao.avisado_em = agora
            avisadas += 1
        else:
            logger.warning("Aviso da execução %s da rotina não enviado.", execucao.id)
            break  # tenta no ciclo seguinte
    db.commit()
    return avisadas


def _ultima_execucao(db: Session) -> datetime | None:
    datas = [db.query(func.max(ExecucaoRotina.terminada_em)).scalar(),
             db.query(func.max(AtualizacaoCaixa.iniciada_em)).scalar()]
    datas = [d for d in datas if d is not None]
    return max(datas) if datas else None


def avisar_rotina_parada(db: Session, agora: datetime | None = None) -> bool:
    """Avisa (no máximo uma vez por dia) se não há execuções há demasiados dias."""
    if not servico_email.email_configurado():
        return False
    agora = agora or datetime.utcnow()
    ultima = _ultima_execucao(db)
    if ultima is None or agora - ultima < timedelta(days=dias_sem_execucao()):
        return False
    aviso = db.query(AvisoSistema).filter(AvisoSistema.tipo == AVISO_ROTINA_PARADA).first()
    if aviso and agora - aviso.enviado_em < timedelta(days=1):
        return False
    admins = _admins(db)
    if not admins:
        return False
    dias = (agora - ultima).days
    linhas = [
        f"A rotina da Caixa não corre há {dias} dias (última execução em {ultima:%d/%m/%Y %H:%M} UTC).",
        "",
        "A tarefa \"Radar Leilao - listas Caixa\" corre às terças e sextas às 15:00 no computador do "
        "administrador, só com a sessão do Windows iniciada e fora da bateria.",
        "Verifique se o computador esteve ligado e se a tarefa está ativa no Agendador de Tarefas. "
        "Sem ela, as listas e as datas dos leilões deixam de ser atualizadas.",
    ]
    if not _enviar_a_todos(admins, f"Radar Leilão: a rotina da Caixa não corre há {dias} dias", linhas):
        return False
    if aviso:
        aviso.enviado_em = agora
    else:
        db.add(AvisoSistema(tipo=AVISO_ROTINA_PARADA, enviado_em=agora))
    db.commit()
    return True
