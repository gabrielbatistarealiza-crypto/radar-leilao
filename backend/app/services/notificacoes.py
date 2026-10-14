from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.criterio_alerta import CriterioAlerta
from app.models.notificacao import Notificacao
from app.models.usuario import Usuario


_LOCK_SCHEDULER_NOTIFICACOES = 724190381


def tentar_lock_scheduler_notificacoes(db: Session) -> bool:
    """Eleger um único worker PostgreSQL para manter o scheduler ativo."""
    if db.get_bind().dialect.name != "postgresql":
        return True
    bloqueado = bool(db.execute(
        text("SELECT pg_try_advisory_lock(:lock_id)"),
        {"lock_id": _LOCK_SCHEDULER_NOTIFICACOES},
    ).scalar())
    # O lock é de sessão e sobrevive ao commit; deixa a ligação sem transação
    # aberta enquanto o worker aguarda o próximo ciclo.
    db.commit()
    return bloqueado


def libertar_lock_scheduler_notificacoes(db: Session) -> None:
    """Libertar o lock de sessão PostgreSQL ao encerrar o worker líder."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": _LOCK_SCHEDULER_NOTIFICACOES},
        )


def gerar_notificacoes(db: Session, agora: date | None = None) -> int:
    """Persiste novas correspondências e prazos próximos para cada utilizador."""
    from app.routers.alertas import listar_correspondencias

    hoje = agora or date.today()
    usuarios_criterios = (
        db.query(CriterioAlerta.usuario_id)
        .filter(CriterioAlerta.ativo.is_(True))
        .distinct()
        .all()
    )
    criadas = 0
    for (usuario_id,) in usuarios_criterios:
        criterios = db.query(CriterioAlerta).filter(
            CriterioAlerta.usuario_id == usuario_id,
            CriterioAlerta.ativo.is_(True),
        ).all()
        usuario = db.get(Usuario, usuario_id)
        if usuario is None:
            continue

        for item in listar_correspondencias(db, usuario):
            imovel = item["imovel"]
            eventos = []
            if item["corresponde"]:
                eventos.append(Notificacao(
                    usuario_id=usuario_id,
                    imovel_id=imovel["id"],
                    evento="correspondencia",
                    tipo="oportunidade",
                    titulo="Nova oportunidade compatível",
                    mensagem=f"{imovel['titulo']} corresponde aos seus critérios de alerta.",
                ))

            criterio = next((c for c in criterios if c.id == item["criterio_id"]), None)
            if criterio:
                for nome, campo in (("primeiro", "data_primeiro_leilao"), ("segundo", "data_segundo_leilao")):
                    data_leilao = imovel.get(campo)
                    if data_leilao is None:
                        continue
                    if isinstance(data_leilao, str):
                        data_leilao = date.fromisoformat(data_leilao)
                    dias = (data_leilao - hoje).days
                    if 0 <= dias <= criterio.alertar_prazos_dias:
                        eventos.append(Notificacao(
                            usuario_id=usuario_id,
                            imovel_id=imovel["id"],
                            evento=f"prazo:{nome}:{data_leilao.isoformat()}",
                            tipo="prazo",
                            titulo="Leilão se aproxima",
                            mensagem=f"{imovel['titulo']}: {nome} leilão em {dias} dia(s), em {data_leilao.isoformat()}.",
                        ))

            for notificacao in eventos:
                try:
                    with db.begin_nested():
                        db.add(notificacao)
                        db.flush()
                    criadas += 1
                except IntegrityError:
                    # A restrição única também protege contra duas instâncias do worker.
                    continue
    db.commit()
    return criadas
