from threading import Lock


# Mantém no máximo uma coleta do site da CAIXA ativa por processo.
CAIXA_COLETA_LOCK = Lock()
