// Aviso para imóveis que saíram da lista da Caixa (continuam na base, fora da pesquisa).
// A API envia saiu_da_lista_em em UTC sem fuso ("2026-10-29T22:14:15"); usa-se só a data.
export function avisoForaDaLista(imovel) {
  if (!imovel || imovel.na_lista !== false) return "";
  const dia = String(imovel.saiu_da_lista_em || "").slice(0, 10).split("-");
  const quando = dia.length === 3 && dia[0].length === 4 ? ` em ${dia[2]}/${dia[1]}/${dia[0]}` : "";
  return `Este imóvel saiu da lista da Caixa${quando}. Pode já ter sido vendido ou retirado.`;
}
