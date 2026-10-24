"""Router FastAPI da consultoria sobre leilões.

Coloque este arquivo e o consultoria_core.py em backend/app/routers/ e registre
no main.py:

    from app.routers.consultoria import criar_router as criar_router_consultoria
    from app.security.auth import usuario_atual

    app.include_router(criar_router_consultoria(usuario_atual))

Variáveis de ambiente:
    ANTHROPIC_API_KEY   obrigatória (nunca vai para o frontend)
    ANTHROPIC_MODEL     opcional, padrão claude-sonnet-5-5
"""
from __future__ import annotations

import os
import logging
import time
import unicodedata
from collections import defaultdict, deque
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .consultoria_core import (
    AVISO_LEGAL,
    MAX_PERGUNTA,
    PerguntaInvalida,
    montar_mensagens,
    montar_system,
)

MODELO_PADRAO = "claude-sonnet-5-5"
MAX_TOKENS_RESPOSTA = 800
LIMITE_PERGUNTAS = 20
JANELA_SEGUNDOS = 10 * 60

logger = logging.getLogger(__name__)


class Mensagem(BaseModel):
    role: str
    content: str = Field(max_length=4000)


class PerguntaEntrada(BaseModel):
    pergunta: str = Field(min_length=1, max_length=MAX_PERGUNTA * 2)
    historico: list[Mensagem] = Field(default_factory=list, max_length=40)
    imovel: dict[str, Any] | None = None


class RespostaSaida(BaseModel):
    resposta: str
    aviso: str


class LimiteDeUso:
    """Limite simples em memória (por processo). Troque por Redis se escalar."""

    def __init__(
        self,
        limite: int = LIMITE_PERGUNTAS,
        janela: int = JANELA_SEGUNDOS,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limite = limite
        self.janela = janela
        self.relogio = relogio
        self._usos: dict[Any, deque[float]] = defaultdict(deque)

    def permitir(self, chave: Any) -> bool:
        agora = self.relogio()
        fila = self._usos[chave]
        while fila and agora - fila[0] > self.janela:
            fila.popleft()
        if len(fila) >= self.limite:
            return False
        fila.append(agora)
        return True


def _id_usuario(usuario: Any) -> Any:
    if isinstance(usuario, dict):
        return usuario.get("id")
    return getattr(usuario, "id", None)


def cliente_anthropic_padrao():
    """Cria o cliente Anthropic ou aponta o SDK ao Ollama local."""
    provedor = os.getenv("CONSULTORIA_PROVEDOR", "anthropic").strip().lower()
    if provedor == "ollama":
        import anthropic

        return anthropic.Anthropic(
            api_key="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        )
    if provedor != "anthropic":
        raise HTTPException(
            status_code=503, detail="Provedor da consultoria não configurado."
        )

    chave = os.getenv("ANTHROPIC_API_KEY")
    if not chave:
        raise HTTPException(
            status_code=503, detail="Consultoria indisponível no momento."
        )
    import anthropic  # import tardio: o resto do backend não depende do SDK

    return anthropic.Anthropic(api_key=chave)


def _texto_da_resposta(mensagem: Any) -> str:
    partes = [
        bloco.text
        for bloco in getattr(mensagem, "content", [])
        if getattr(bloco, "type", None) == "text"
    ]
    return "".join(partes).strip()


def _modo_simulado() -> bool:
    return os.getenv("CONSULTORIA_MODO_SIMULADO", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _resposta_simulada() -> str:
    return (
        "RESPOSTA SIMULADA — esta mensagem serve apenas para testar a tela; "
        "nenhuma IA foi consultada.\n\n"
        "Além do lance, podem existir comissão do leiloeiro, ITBI, custos de "
        "escritura e registro, débitos previstos no edital, despesas de "
        "desocupação e reparos. Os itens e valores dependem do imóvel e das "
        "regras do leilão; confira o edital antes de decidir."
    )


def _pergunta_sfi_edital_unico(pergunta: str) -> bool:
    normalizada = unicodedata.normalize("NFKD", pergunta.lower())
    normalizada = "".join(c for c in normalizada if not unicodedata.combining(c))
    return "sfi" in normalizada and "edital unico" in normalizada


def _pergunta_pontos_edital(pergunta: str) -> bool:
    normalizada = unicodedata.normalize("NFKD", pergunta.lower())
    normalizada = "".join(c for c in normalizada if not unicodedata.combining(c))
    return "pontos do edital" in normalizada and "lance" in normalizada


def _pergunta_custos_alem_lance(pergunta: str) -> bool:
    normalizada = unicodedata.normalize("NFKD", pergunta.lower())
    normalizada = "".join(c for c in normalizada if not unicodedata.combining(c))
    return "custos" in normalizada and "lance" in normalizada and "alem" in normalizada


def _pergunta_divida_condominio(pergunta: str) -> bool:
    normalizada = unicodedata.normalize("NFKD", pergunta.lower())
    normalizada = "".join(c for c in normalizada if not unicodedata.combining(c))
    menciona_condominio = "condominio" in normalizada
    menciona_debito = any(palavra in normalizada for palavra in ("divida", "debito", "quem paga", "responsavel"))
    menciona_leilao = any(palavra in normalizada for palavra in ("leilao", "arrematacao", "edital"))
    return menciona_condominio and menciona_debito and menciona_leilao


def _pergunta_condicoes_pagamento(pergunta: str) -> bool:
    """Identifica pedidos sobre forma, entrada, prazo ou parcelamento."""
    normalizada = unicodedata.normalize("NFKD", pergunta.lower())
    normalizada = "".join(c for c in normalizada if not unicodedata.combining(c))
    termos = (
        "pagamento", "entrada", "parcelamento", "parcelado", "parcelas",
        "financiamento", "fgts", "recursos proprios", "saldo",
        "prazo de pagamento", "prazo para pagar", "prazo pra pagar",
        "tempo para pagar", "tempo pra pagar",
    )
    return any(termo in normalizada for termo in termos)


def _resposta_pagamento_generica() -> str:
    return (
        "De forma geral, as formas e os prazos de pagamento variam conforme "
        "o leilão e o imóvel. O anúncio do lote informa quais opções são aceitas; "
        "não há percentual de entrada ou parcelamento que possa ser presumido "
        "para todos os casos. Confirme as condições no anúncio e, se houver "
        "financiamento ou FGTS, verifique antes se você e o imóvel se enquadram."
    )


def _pergunta_texto_especifico_edital(pergunta: str) -> bool:
    """Identifica pedidos para localizar cláusula ou texto do edital."""
    normalizada = unicodedata.normalize("NFKD", pergunta.lower())
    normalizada = "".join(c for c in normalizada if not unicodedata.combining(c))
    return "clausul" in normalizada or any(
        termo in normalizada for termo in ("o que diz o edital", "texto do edital")
    )


def _resposta_sfi_edital_unico() -> str:
    return (
        "Na oferta identificada como Leilão SFI, a venda costuma seguir o "
        "procedimento extrajudicial ligado à alienação fiduciária (Lei "
        "9.514/1997), diferente de uma arrematação judicial. Não presuma que "
        "vale o parcelamento judicial de 25% de entrada e saldo em até 30 meses "
        "do art. 895 do CPC. O termo ‘Edital Único’ não garante condições iguais "
        "para todos os imóveis: confira no edital desta oferta as datas e valores "
        "dos leilões, forma e prazo de pagamento, comissão, débitos, ocupação e "
        "regras de financiamento ou FGTS."
    )


def _resposta_pontos_edital() -> str:
    return (
        "Antes de dar o lance, confira no edital: datas e valor mínimo; forma e "
        "prazo de pagamento; comissão do leiloeiro e consequências do atraso; "
        "possibilidade e condições de financiamento ou uso do FGTS; quem assume "
        "IPTU, condomínio e outros débitos; situação de ocupação e regras para "
        "desocupação; além de eventuais ações, restrições e custos de registro. "
        "Compare essas condições com a matrícula atualizada do imóvel. Se algo "
        "não estiver claro, confirme com o leiloeiro e, para questões jurídicas, "
        "com o advogado da nossa equipe. As regras variam entre leilões."
    )


def _resposta_custos_alem_lance() -> str:
    return (
        "Além do lance, verifique no edital a comissão do leiloeiro e o valor "
        "ou percentual aplicável; ITBI e despesas de cartório/registro; custos "
        "de financiamento, se houver; débitos de IPTU e condomínio e quem será "
        "responsável por eles; e possíveis gastos com desocupação e reparos. "
        "Percentuais, valores e responsabilidades variam conforme o imóvel e "
        "as regras do leilão. Confirme os itens incertos com o nosso advogado."
    )


def _resposta_divida_condominio() -> str:
    return (
        "Não há uma resposta única para todo leilão. O art. 1.345 do Código "
        "Civil prevê que o adquirente de uma unidade pode responder por débitos "
        "condominiais do antigo proprietário. Em leilão judicial, a análise "
        "também depende do que o edital informou: a jurisprudência do STJ "
        "considera a previsão ou ciência expressa dos débitos e, em certas "
        "situações, a sub-rogação no preço da arrematação. Em venda extrajudicial, "
        "confira as regras e documentos específicos da operação. Antes do lance, "
        "peça ao condomínio um demonstrativo atualizado e verifique no edital "
        "quem assume os débitos anteriores. Se houver dúvida, consulte o advogado "
        "da nossa equipe."
    )


def criar_router(
    get_usuario_atual: Callable[..., Any],
    get_cliente: Callable[..., Any] = cliente_anthropic_padrao,
    limite: LimiteDeUso | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/consultoria", tags=["consultoria"])
    controle = limite or LimiteDeUso()

    @router.post("/perguntar", response_model=RespostaSaida)
    def perguntar(
        entrada: PerguntaEntrada,
        usuario: Any = Depends(get_usuario_atual),
    ) -> RespostaSaida:
        try:
            # O histórico da conversa vai para o modelo (ordem e papéis
            # preservados); sanitizar_historico mantém só user/assistant, as
            # últimas mensagens e começa sempre por "user". Os dados do imóvel
            # continuam fora do pedido (ver comentário mais abaixo).
            mensagens = montar_mensagens(
                [mensagem.model_dump() for mensagem in entrada.historico],
                entrada.pergunta,
            )
        except PerguntaInvalida as erro:
            raise HTTPException(status_code=422, detail=str(erro)) from erro

        if not controle.permitir(_id_usuario(usuario)):
            raise HTTPException(
                status_code=429,
                detail="Muitas perguntas em pouco tempo. Tente novamente em alguns minutos.",
            )

        if _modo_simulado():
            return RespostaSaida(resposta=_resposta_simulada(), aviso=AVISO_LEGAL)

        if _pergunta_condicoes_pagamento(entrada.pergunta):
            return RespostaSaida(
                resposta=_resposta_pagamento_generica(),
                aviso=(
                    AVISO_LEGAL
                    + " Resposta geral; não confirma as condições deste imóvel."
                ),
            )

        # A consultoria foi configurada para oferecer orientação geral. Não usa
        # dados do imóvel, edital ou anúncio para evitar apresentar regras gerais
        # como se fossem condições confirmadas deste lote.
        if _pergunta_texto_especifico_edital(entrada.pergunta):
            return RespostaSaida(
                resposta=(
                    "Posso explicar de forma geral o que costuma aparecer em um edital, "
                    "mas não confirmar cláusulas deste imóvel. Em geral, confira "
                    "identificação do lote, datas, pagamento, comissão, débitos, "
                    "ocupação, financiamento e responsabilidades do comprador. "
                    "As regras variam entre leilões."
                ),
                aviso=AVISO_LEGAL,
            )

        if _pergunta_sfi_edital_unico(entrada.pergunta):
            return RespostaSaida(
                resposta=_resposta_sfi_edital_unico(), aviso=AVISO_LEGAL
            )

        if _pergunta_pontos_edital(entrada.pergunta):
            return RespostaSaida(
                resposta=_resposta_pontos_edital(), aviso=AVISO_LEGAL
            )

        if _pergunta_custos_alem_lance(entrada.pergunta):
            return RespostaSaida(
                resposta=_resposta_custos_alem_lance(), aviso=AVISO_LEGAL
            )

        if _pergunta_divida_condominio(entrada.pergunta):
            return RespostaSaida(
                resposta=_resposta_divida_condominio(), aviso=AVISO_LEGAL
            )

        try:
            system = montar_system()
            system += (
                "\nEsta consultoria responde sempre em caráter geral. Ignore dados "
                "de imóveis específicos, inclusive códigos de lote citados na pergunta. "
                "Nunca comece com 'para o lote X' nem use dados da oferta como fatos. "
                "Não afirme que consultou edital, anúncio ou documentação; não atribua regras, "
                "valores, datas, condições ou responsabilidades a um lote específico. "
                "Explique o que costuma ocorrer, ressalve que varia entre leilões e "
                "oriente a confirmação nos documentos da oferta."
            )
            aviso_resposta = AVISO_LEGAL

            if os.getenv("CONSULTORIA_PROVEDOR", "anthropic").strip().lower() == "ollama":
                # Use a API nativa para enviar think=false; na compatibilidade
                # Anthropic o modelo local pode devolver o raciocínio como texto.
                import httpx

                system += (
                    "\nResponda somente em português do Brasil, em até 180 palavras. "
                    "Entregue apenas a resposta final, sem narrar raciocínio."
                )
                mensagens_ollama = [{"role": "system", "content": system}, *mensagens]
                base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
                resposta_http = httpx.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": os.getenv("ANTHROPIC_MODEL", MODELO_PADRAO),
                        "messages": mensagens_ollama,
                        "think": False,
                        "stream": False,
                        "options": {"num_predict": 500},
                    },
                    timeout=120.0,
                )
                resposta_http.raise_for_status()
                texto = resposta_http.json().get("message", {}).get("content", "").strip()
            else:
                # Só inicializa o cliente externo quando a pergunta realmente
                # precisa de geração. Respostas determinísticas e fallback sem
                # evidência continuam disponíveis sem chave de API.
                cliente = get_cliente()
                resposta = cliente.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", MODELO_PADRAO),
                    max_tokens=MAX_TOKENS_RESPOSTA,
                    system=system,
                    messages=mensagens,
                )
                texto = _texto_da_resposta(resposta)
        except HTTPException:
            raise
        except Exception as erro:  # erros do SDK: rede, limite, serviço
            nome = type(erro).__name__
            logger.warning(
                "Falha na API da consultoria: tipo=%s status=%s request_id=%s",
                nome,
                getattr(erro, "status_code", None),
                getattr(erro, "request_id", None),
            )
            if "RateLimit" in nome or "Overloaded" in nome:
                raise HTTPException(
                    status_code=503,
                    detail="A consultoria está ocupada. Tente novamente em instantes.",
                ) from erro
            raise HTTPException(
                status_code=502,
                detail="Não foi possível obter a resposta da consultoria.",
            ) from erro

        if not texto:
            raise HTTPException(
                status_code=502, detail="A consultoria não retornou uma resposta."
            )
        return RespostaSaida(
            resposta=texto,
            aviso=aviso_resposta,
        )

    return router
