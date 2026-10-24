"""Create a disposable SQLite fixture for the Flutter Android smoke test."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
DATABASE_FILE = REPO_DIR / "work" / "mobile-validation.sqlite3"
DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Set these before importing the app. They take precedence over backend/.env.
os.environ["DATABASE_URL"] = f"sqlite:///{DATABASE_FILE.as_posix()}"
os.environ["SECRET_KEY"] = "local-mobile-validation-only"
os.environ["RADAR_TEST_DISABLE_BACKGROUND_JOBS"] = "1"
sys.path.insert(0, str(BACKEND_DIR))

from app.database.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402,F401
from app.models.imovel import Imovel  # noqa: E402
from app.models.imovel import ImovelImagem  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.models.notificacao import Notificacao  # noqa: E402
from app.security.password import gerar_hash  # noqa: E402


TEST_EMAIL = "mobile.test@example.com"
TEST_PASSWORD = "MobileTest-2026!"
OTHER_TEST_EMAIL = "mobile.other@example.com"
OTHER_TEST_PASSWORD = "MobileOther-2026!"
PROPERTY_TITLE = "Imóvel Sintético Mobile - Teste"


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter_by(email=TEST_EMAIL).first()
        if user is None:
            user = Usuario(
                nome="Usuário Mobile de Teste",
                email=TEST_EMAIL,
                senha=gerar_hash(TEST_PASSWORD),
                admin=False,
                tipo="cliente",
            )
            db.add(user)
        else:
            user.senha = gerar_hash(TEST_PASSWORD)

        other_user = db.query(Usuario).filter_by(email=OTHER_TEST_EMAIL).first()
        if other_user is None:
            other_user = Usuario(
                nome="Segundo Usuário Mobile de Teste",
                email=OTHER_TEST_EMAIL,
                senha=gerar_hash(OTHER_TEST_PASSWORD),
                admin=False,
                tipo="cliente",
            )
            db.add(other_user)
        else:
            other_user.senha = gerar_hash(OTHER_TEST_PASSWORD)

        prop = db.query(Imovel).filter_by(titulo=PROPERTY_TITLE).first()
        if prop is None:
            prop = Imovel(titulo=PROPERTY_TITLE)
            db.add(prop)
        prop.tipo = "Apartamento"
        prop.endereco = "Rua de Teste, 123"
        prop.cidade = "Lisboa"
        prop.estado = "SP"
        prop.valor_avaliacao = 200000
        prop.valor_leilao = 120000
        prop.desconto = 40
        prop.area = 70
        prop.quartos = 2
        prop.banheiros = 1
        prop.vagas = 1
        prop.data_primeiro_leilao = date(2099, 1, 1)
        prop.modalidade = "Leilão SFI - Edital Único"
        prop.fonte = "fixture sintético"
        prop.url = "https://example.invalid/test"
        prop.fotos.clear()
        prop.fotos.extend([
            ImovelImagem(url="https://example.invalid/foto-1.jpg", ordem=0),
            ImovelImagem(url="https://example.invalid/foto-2.jpg", ordem=1),
        ])
        db.commit()
        for owner, event in ((user, "mobile-smoke:own"), (other_user, "mobile-smoke:other")):
            notification = db.query(Notificacao).filter_by(
                usuario_id=owner.id, imovel_id=prop.id, evento=event
            ).first()
            if notification is None:
                db.add(Notificacao(
                    usuario_id=owner.id,
                    imovel_id=prop.id,
                    evento=event,
                    tipo="oportunidade",
                    titulo="Notificação sintética de teste",
                    mensagem="Esta notificação existe somente na base SQLite de validação.",
                    lida=False,
                ))
            else:
                notification.lida = False
        db.commit()
    finally:
        db.close()

    print(f"SQLite de teste: {DATABASE_FILE}")
    print(f"Login sintético: {TEST_EMAIL} / {TEST_PASSWORD}")
    print(f"Segundo login sintético: {OTHER_TEST_EMAIL} / {OTHER_TEST_PASSWORD}")
    print(f"Imóvel esperado: {PROPERTY_TITLE}")
    print("Jobs de fundo e scraping automático: desativados")


if __name__ == "__main__":
    main()
