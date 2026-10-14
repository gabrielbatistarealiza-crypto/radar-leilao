"""Create the first administrator from an explicitly selected database.

Run from the backend directory with: python -m scripts.bootstrap_admin
PostgreSQL requires the explicit --allow-production flag. DATABASE_URL must
be set in the environment. The displayed target must be confirmed before any
credential prompt or database connection.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy.engine import make_url


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Criar o primeiro administrador")
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Confirma explicitamente o uso do PostgreSQL indicado em DATABASE_URL.",
    )
    return parser.parse_args()


def _credentials() -> tuple[str, str, str]:
    nome = os.getenv("BOOTSTRAP_ADMIN_NAME") or input("Nome do administrador: ").strip()
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL") or input("E-mail do administrador: ").strip()
    senha = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if senha is None:
        senha = getpass.getpass("Senha do administrador (mínimo 12 caracteres): ")
        confirmacao = getpass.getpass("Confirme a senha: ")
        if senha != confirmacao:
            raise ValueError("As senhas não coincidem.")

    if not nome:
        raise ValueError("O nome é obrigatório.")
    if not email or "@" not in email:
        raise ValueError("Informe um e-mail válido.")
    if len(senha) < 12:
        raise ValueError("A senha deve ter pelo menos 12 caracteres.")
    return nome, email, senha


def main() -> int:
    args = _arguments()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "Operação recusada: defina DATABASE_URL explicitamente no ambiente "
            "para inspecionar o alvo; o .env não é aceito como seleção implícita.",
            file=sys.stderr,
        )
        return 2
    if database_url.startswith("postgres://"):
        database_url = "postgresql://" + database_url[len("postgres://"):]

    try:
        target = make_url(database_url)
    except Exception:
        print("Operação recusada: DATABASE_URL inválida.", file=sys.stderr)
        return 2

    dialect = target.get_backend_name()
    host = target.host or "(local)"
    database = target.database or "(não informado)"
    print(f"Alvo selecionado: dialeto={dialect}; host={host}; banco={database}")

    if dialect not in {"sqlite", "postgresql"}:
        print("Operação recusada: somente SQLite ou PostgreSQL são aceitos.", file=sys.stderr)
        return 2
    if dialect == "postgresql" and not args.allow_production:
        print(
            "Operação recusada: PostgreSQL exige a opção --allow-production "
            "na linha de comando.",
            file=sys.stderr,
        )
        return 2

    try:
        confirmacao_alvo = input(
            "Confirma este alvo exatamente como exibido? Digite SIM para continuar: "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        print("Operação cancelada; nenhuma conexão foi aberta.", file=sys.stderr)
        return 1
    if confirmacao_alvo != "SIM":
        print("Operação cancelada; nenhuma conexão foi aberta.", file=sys.stderr)
        return 1

    # Import only after inspecting, validating, and confirming the target.
    from sqlalchemy import func, insert, select, text

    from app.database.database import engine
    from app.models.usuario import Usuario
    from app.security.password import gerar_hash

    if engine.dialect.name != dialect:
        print("Operação recusada: o banco carregado não corresponde ao alvo inspecionado.", file=sys.stderr)
        return 2

    try:
        nome, email, senha = _credentials()
    except (EOFError, KeyboardInterrupt):
        print("Operação cancelada.", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    connection = engine.connect()
    try:
        if engine.dialect.name == "sqlite":
            # Serialize competing bootstrap attempts before checking the table.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
            connection.execute(text("LOCK TABLE usuarios IN ACCESS EXCLUSIVE MODE"))

        quantidade = connection.scalar(
            select(func.count()).select_from(Usuario.__table__)
        )
        if quantidade:
            connection.rollback()
            print(
                f"Operação recusada: a tabela usuarios já contém {quantidade} registro(s).",
                file=sys.stderr,
            )
            return 3

        connection.execute(
            insert(Usuario.__table__).values(
                nome=nome,
                email=email,
                senha=gerar_hash(senha),
                admin=True,
                tipo="admin",
            )
        )
        connection.commit()
        print("Administrador inicial criado com sucesso.")
        return 0
    except Exception:
        connection.rollback()
        print(
            "Falha ao criar o administrador. Confira o esquema e a conexão; "
            "nenhuma senha foi exibida.",
            file=sys.stderr,
        )
        return 1
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
