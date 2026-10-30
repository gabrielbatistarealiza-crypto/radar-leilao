// Cliente único da API: endereço, token e erros num só sítio.
// (Fase 5: antes, cada ecrã definia o seu próprio API_URL.)

export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export const CHAVE_TOKEN = "radar-leilao-token";

// A API devolve detail como texto ou, na validação, como lista de erros.
export function mensagemDeErro(dados, padrao) {
  const detalhe = dados?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe) && detalhe.length) {
    const msg = String(detalhe[0]?.msg || "");
    return msg.replace(/^Value error,\s*/i, "") || padrao;
  }
  return padrao;
}

export class ErroApi extends Error {
  constructor(mensagem, status, dados) {
    super(mensagem);
    this.name = "ErroApi";
    this.status = status;
    this.dados = dados;
  }
}

/**
 * Pede `caminho` à API e devolve o JSON da resposta.
 * Em erro HTTP lança ErroApi com a mensagem da API (ou `erroPadrao`).
 * `corpo` (objeto) vai como JSON; `token` vai como Bearer.
 */
export async function pedirApi(caminho, { metodo = "GET", corpo, token, sinal, erroPadrao } = {}) {
  const cabecalhos = {};
  if (corpo !== undefined) cabecalhos["Content-Type"] = "application/json";
  if (token) cabecalhos.Authorization = `Bearer ${token}`;

  const resposta = await fetch(`${API_URL}${caminho}`, {
    method: metodo,
    headers: cabecalhos,
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
    signal: sinal,
  });
  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    throw new ErroApi(
      mensagemDeErro(dados, erroPadrao || `Erro HTTP ${resposta.status}`),
      resposta.status,
      dados
    );
  }
  return dados;
}
