// Sessão: quando o token expira (60 min) ou a API o recusa, o site volta ao
// ecrã de entrada em vez de ficar aberto com todos os pedidos a falhar.
import { API_URL } from "./api";

export const AVISO_SESSAO_EXPIRADA = "A sua sessão expirou. Entre outra vez para continuar.";

/** Momento (ms) em que o token expira, lido do próprio JWT; null se não der para ler. */
export function expiraEm(token) {
  try {
    const parte = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const dados = JSON.parse(atob(parte.padEnd(parte.length + ((4 - (parte.length % 4)) % 4), "=")));
    return typeof dados.exp === "number" ? dados.exp * 1000 : null;
  } catch {
    return null;
  }
}

function levaSessao(opcoes) {
  const cabecalhos = opcoes?.headers;
  if (!cabecalhos) return false;
  const valor = typeof cabecalhos.get === "function"
    ? cabecalhos.get("Authorization")
    : cabecalhos.Authorization || cabecalhos.authorization;
  return typeof valor === "string" && valor.startsWith("Bearer ");
}

/**
 * Vigia a sessão: chama `aoExpirar` quando um pedido COM sessão à API devolve
 * 401, ou quando chega a hora de expiração do token. Devolve a função que
 * desliga a vigia (repõe o fetch original e cancela o temporizador).
 */
export function vigiarSessao(token, aoExpirar) {
  const fetchOriginal = window.fetch;
  let avisado = false;
  const expirar = () => {
    if (!avisado) {
      avisado = true;
      aoExpirar();
    }
  };

  window.fetch = async (recurso, opcoes) => {
    const resposta = await fetchOriginal(recurso, opcoes);
    const url = typeof recurso === "string" ? recurso : recurso?.url || "";
    if (resposta?.status === 401 && levaSessao(opcoes) && String(url).startsWith(API_URL)) {
      expirar();
    }
    return resposta;
  };

  let temporizador = null;
  const fim = expiraEm(token);
  if (fim !== null) {
    // setTimeout não aceita mais de ~24,8 dias; os tokens daqui duram 60 min.
    const espera = Math.min(Math.max(fim - Date.now(), 0), 2 ** 31 - 1);
    temporizador = setTimeout(expirar, espera);
  }

  return () => {
    window.fetch = fetchOriginal;
    if (temporizador !== null) clearTimeout(temporizador);
  };
}
