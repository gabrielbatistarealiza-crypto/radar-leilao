// Ritmo do ciclo manual de datas da CAIXA no painel Admin.
//
// Antes: 5 imóveis por pedido e 1,5 s entre pedidos, muito mais depressa do
// que o worker automático, o que levava rapidamente a CAPTCHA.
// Agora: 1 imóvel por pedido e a mesma pausa do worker (intervalo_segundos
// devolvido por GET /caixa/enriquecer-datas/status).

export const LIMITE_POR_PEDIDO = 1;
export const INTERVALO_PADRAO_SEGUNDOS = 60;
export const INTERVALO_MINIMO_SEGUNDOS = 10;

// Lê o intervalo do status do backend; valores ausentes ou inválidos usam o
// padrão e nunca se desce abaixo do mínimo.
export function intervaloDoStatus(status) {
  const valor = Number(status?.intervalo_segundos);
  if (!Number.isFinite(valor) || valor <= 0) return INTERVALO_PADRAO_SEGUNDOS;
  return Math.max(INTERVALO_MINIMO_SEGUNDOS, Math.floor(valor));
}

// Decide o que fazer depois de um pedido ao endpoint de datas.
// pausa: "bloqueio" | "falha_tecnica" | "erro" | null
// fim: true quando já não há imóveis pendentes.
export function avaliarLote(resultado) {
  const resultados = Array.isArray(resultado?.resultados) ? resultado.resultados : [];
  let proximoCursor = resultado?.proximo_depois_id
    ? Number(resultado.proximo_depois_id)
    : null;

  const itemBloqueado = resultados.find((item) => item.status === "BLOQUEADO_CAIXA");
  if (resultado?.bloqueado) {
    if (itemBloqueado) proximoCursor = Math.max(0, Number(itemBloqueado.id) - 1);
    return { proximoCursor, pausa: "bloqueio", fim: false };
  }

  // A página não foi lida (Chrome, timeouts): fica antes deste imóvel para o
  // retomar mais tarde, em vez de o saltar.
  if (resultado?.falha_tecnica) {
    const id = Number(resultado.falha_tecnica_id);
    if (Number.isFinite(id)) proximoCursor = Math.max(0, id - 1);
    return { proximoCursor, pausa: "falha_tecnica", fim: false };
  }

  const comErro = resultados
    .filter((item) => item.status === "ERRO")
    .map((item) => Number(item.id))
    .filter(Number.isFinite);
  if (Number(resultado?.erros || 0) && comErro.length) {
    return {
      proximoCursor: Math.max(0, Math.min(...comErro) - 1),
      pausa: "erro",
      fim: false,
    };
  }

  const fim = !resultado?.tem_mais || Number(resultado?.processados || 0) === 0;
  return { proximoCursor, pausa: null, fim };
}

// Espera `segundos`, verificando a cada segundo se foi pedida a paragem.
// Devolve true se parou antes do fim. `aoTic` recebe os segundos que faltam.
export async function aguardarComParagem(
  segundos,
  deveParar,
  { aoTic = () => {}, dormir = (ms) => new Promise((r) => setTimeout(r, ms)) } = {}
) {
  for (let restante = segundos; restante > 0; restante -= 1) {
    if (deveParar()) return true;
    aoTic(restante);
    await dormir(1000);
  }
  return deveParar();
}
