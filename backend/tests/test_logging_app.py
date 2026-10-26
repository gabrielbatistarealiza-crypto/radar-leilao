"""As mensagens INFO da app tem de aparecer com a configuracao de logging do uvicorn."""
import io
import logging
import logging.config

import pytest
import uvicorn.config


@pytest.fixture
def saida_do_logger_da_app(monkeypatch):
    """Configura o logging como o uvicorn faz e devolve o texto escrito pelo handler da app."""
    monkeypatch.setenv("RADAR_DISABLE_BACKGROUND_JOBS", "1")
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)

    from app import main

    main.configurar_logging_da_app()
    handler = next(h for h in logging.getLogger("app").handlers if getattr(h, "_radar_logging", False))
    buffer = io.StringIO()
    anterior = handler.setStream(buffer)
    try:
        yield main, buffer
    finally:
        handler.setStream(anterior)


def test_logger_da_app_mostra_info_com_a_configuracao_do_uvicorn(saida_do_logger_da_app):
    _, buffer = saida_do_logger_da_app

    logging.getLogger("app.services.exemplo").info("mensagem de teste INFO")

    assert logging.getLogger("app.main").isEnabledFor(logging.INFO)
    assert "app.services.exemplo: mensagem de teste INFO" in buffer.getvalue()


def test_configurar_logging_nao_duplica_o_handler(saida_do_logger_da_app):
    main, _ = saida_do_logger_da_app

    main.configurar_logging_da_app()
    main.configurar_logging_da_app()

    handlers = [h for h in logging.getLogger("app").handlers if getattr(h, "_radar_logging", False)]
    assert len(handlers) == 1


def test_lifespan_regista_que_as_rotinas_estao_desativadas(saida_do_logger_da_app):
    from fastapi.testclient import TestClient

    main, buffer = saida_do_logger_da_app

    with TestClient(main.app):
        pass

    assert "Rotinas automáticas em segundo plano desativadas por configuração." in buffer.getvalue()
