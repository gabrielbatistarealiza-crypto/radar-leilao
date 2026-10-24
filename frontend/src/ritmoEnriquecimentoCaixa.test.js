import { describe, expect, it, vi } from "vitest";
import {
  INTERVALO_MINIMO_SEGUNDOS,
  INTERVALO_PADRAO_SEGUNDOS,
  LIMITE_POR_PEDIDO,
  aguardarComParagem,
  avaliarLote,
  intervaloDoStatus,
} from "./ritmoEnriquecimentoCaixa";

describe("ritmo do ciclo manual de datas", () => {
  it("consulta um imóvel por pedido", () => {
    expect(LIMITE_POR_PEDIDO).toBe(1);
  });

  it.each([
    [{ intervalo_segundos: 120 }, 120],
    [{ intervalo_segundos: 90.7 }, 90],
    [{ intervalo_segundos: 3 }, INTERVALO_MINIMO_SEGUNDOS],
    [{ intervalo_segundos: "abc" }, INTERVALO_PADRAO_SEGUNDOS],
    [{ intervalo_segundos: 0 }, INTERVALO_PADRAO_SEGUNDOS],
    [{}, INTERVALO_PADRAO_SEGUNDOS],
    [null, INTERVALO_PADRAO_SEGUNDOS],
  ])("intervaloDoStatus(%j) = %i", (status, esperado) => {
    expect(intervaloDoStatus(status)).toBe(esperado);
  });

  it("nunca é mais rápido do que os antigos 1,5 s", () => {
    expect(INTERVALO_MINIMO_SEGUNDOS * 1000).toBeGreaterThan(1500);
  });
});

describe("avaliarLote", () => {
  it("segue para o próximo quando correu bem", () => {
    expect(
      avaliarLote({ processados: 1, tem_mais: true, proximo_depois_id: 42, resultados: [] })
    ).toEqual({ proximoCursor: 42, pausa: null, fim: false });
  });

  it("termina quando não há mais imóveis", () => {
    expect(avaliarLote({ processados: 1, tem_mais: false }).fim).toBe(true);
    expect(avaliarLote({ processados: 0, tem_mais: true }).fim).toBe(true);
  });

  it("pausa no bloqueio e fica antes do imóvel bloqueado", () => {
    expect(
      avaliarLote({
        bloqueado: true,
        proximo_depois_id: 10,
        resultados: [{ id: 10, status: "BLOQUEADO_CAIXA" }],
      })
    ).toEqual({ proximoCursor: 9, pausa: "bloqueio", fim: false });
  });

  it("pausa na falha técnica sem saltar o imóvel", () => {
    expect(
      avaliarLote({
        falha_tecnica: true,
        falha_tecnica_id: 30,
        tem_mais: true,
        proximo_depois_id: 30,
        resultados: [{ id: 30, status: "FALHA_TECNICA" }],
      })
    ).toEqual({ proximoCursor: 29, pausa: "falha_tecnica", fim: false });
  });

  it("pausa no erro e fica antes do primeiro imóvel com erro", () => {
    expect(
      avaliarLote({
        erros: 1,
        tem_mais: true,
        proximo_depois_id: 50,
        resultados: [{ id: 50, status: "ERRO" }],
      })
    ).toEqual({ proximoCursor: 49, pausa: "erro", fim: false });
  });
});

describe("aguardarComParagem", () => {
  it("espera os segundos pedidos, um de cada vez", async () => {
    const dormir = vi.fn(() => Promise.resolve());
    const tics = [];
    const parou = await aguardarComParagem(3, () => false, {
      dormir,
      aoTic: (s) => tics.push(s),
    });
    expect(parou).toBe(false);
    expect(dormir).toHaveBeenCalledTimes(3);
    expect(dormir).toHaveBeenCalledWith(1000);
    expect(tics).toEqual([3, 2, 1]);
  });

  it("para a meio quando é pedida a paragem", async () => {
    let chamadas = 0;
    const dormir = vi.fn(() => Promise.resolve());
    const parou = await aguardarComParagem(60, () => ++chamadas > 2, { dormir });
    expect(parou).toBe(true);
    expect(dormir).toHaveBeenCalledTimes(2);
  });
});
