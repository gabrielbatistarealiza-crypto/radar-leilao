import { describe, expect, it } from "vitest";
import { avisoForaDaLista } from "./foraDaLista";

describe("avisoForaDaLista", () => {
  it("não mostra nada para imóveis na lista ou sem o campo", () => {
    expect(avisoForaDaLista({ na_lista: true })).toBe("");
    expect(avisoForaDaLista({})).toBe("");
    expect(avisoForaDaLista(null)).toBe("");
  });

  it("mostra a data de saída sem mudar de dia por causa do fuso", () => {
    expect(avisoForaDaLista({ na_lista: false, saiu_da_lista_em: "2026-10-29T23:59:00" })).toBe(
      "Este imóvel saiu da lista da Caixa em 29/10/2026. Pode já ter sido vendido ou retirado."
    );
  });

  it("funciona sem data", () => {
    expect(avisoForaDaLista({ na_lista: false, saiu_da_lista_em: null })).toBe(
      "Este imóvel saiu da lista da Caixa. Pode já ter sido vendido ou retirado."
    );
  });
});
