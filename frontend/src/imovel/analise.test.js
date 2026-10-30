import { describe, expect, it } from "vitest";
import {
  alertasDoImovel,
  calcularDesconto,
  calcularEconomia,
  calcularScoreOportunidade,
  dataCivil,
  decisaoDaOportunidade,
  detalhesDoScore,
  valoresDosLeiloes,
  dinheiro,
  formatarData,
  fotosDoImovel,
  valorInputFinanceiro,
} from "./analise";

const BASE = {
  cidade: "CAMPINAS",
  estado: "SP",
  valor_avaliacao: 200000,
  valor_leilao: 100000,
  area: 80,
  data_primeiro_leilao: "2099-01-10",
  data_segundo_leilao: "2099-01-20",
};

describe("formatação", () => {
  it("dinheiro em reais e 'Não informado' quando não há valor", () => {
    expect(dinheiro(1234.5).replace(/\s/g, " ")).toBe("R$ 1.234,50");
    expect(dinheiro(null)).toBe("Não informado");
    expect(dinheiro("abc")).toBe("Não informado");
  });

  it("formatarData e dataCivil não mudam de dia por causa do fuso", () => {
    expect(formatarData("2026-11-30")).toBe("30/11/2026");
    expect(formatarData(null)).toBe("Não informada");
    const d = dataCivil("2026-11-30T23:59:00");
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 10, 30]);
    expect(dataCivil("")).toBeNull();
  });

  it("valorInputFinanceiro com duas casas ou vazio", () => {
    expect(valorInputFinanceiro(10)).toBe("10.00");
    expect(valorInputFinanceiro("x")).toBe("");
  });
});

describe("desconto e economia", () => {
  it("desconto em percentagem; nulo se os valores não fizerem sentido", () => {
    expect(calcularDesconto(BASE)).toBe(50);
    expect(calcularDesconto({ valor_avaliacao: 100, valor_leilao: 150 })).toBeNull();
    expect(calcularDesconto({ valor_avaliacao: 0, valor_leilao: 10 })).toBeNull();
  });

  it("economia nunca é negativa", () => {
    expect(calcularEconomia(BASE)).toBe(100000);
    expect(calcularEconomia({ valor_avaliacao: 100, valor_leilao: 150 })).toBe(0);
    expect(calcularEconomia({})).toBe(0);
  });
});

describe("leilão SFI e valores do edital", () => {
  const SFI = {
    ...BASE,
    modalidade: "Leilão SFI - Edital Único",
    valor_avaliacao: 140000,
    valor_leilao: 140000,
    ocupado: null,
  };

  it("sem edital lido não diz 'Dados insuficientes': o valor do 2.º leilão está por confirmar", () => {
    const d = decisaoDaOportunidade(SFI);
    expect(d.titulo).toBe("Valor do 2.º leilão por confirmar");
    expect(d.classe).toBe("atencao");
    expect(valoresDosLeiloes(SFI)).toBeNull();
  });

  it("com o edital, mostra os dois valores e usa o lance mínimo", () => {
    const comEdital = { ...SFI, valor_primeiro_leilao: 149014, valor_segundo_leilao: 111258.07, valor_leilao: 111258.07 };
    expect(valoresDosLeiloes(comEdital)).toEqual({ primeiro: 149014, segundo: 111258.07, lanceMinimo: 111258.07 });
    expect(calcularDesconto(comEdital)).toBeCloseTo(20.53, 2);
    expect(decisaoDaOportunidade(comEdital).titulo).not.toMatch(/insuficientes|por confirmar/);
  });

  it("edital lido sem desconto: 'Sem desconto'", () => {
    const caro = { ...SFI, valor_primeiro_leilao: 149014, valor_segundo_leilao: 211179, valor_leilao: 149014 };
    expect(decisaoDaOportunidade(caro).titulo).toBe("Sem desconto");
  });

  it("'Dados insuficientes' só quando faltam a avaliação ou o valor do leilão", () => {
    expect(decisaoDaOportunidade({ ...SFI, valor_avaliacao: null }).titulo).toBe("Dados insuficientes");
  });
});

describe("score", () => {
  it("dá um valor de 0 a 100 com classe e texto coerentes", () => {
    const s = calcularScoreOportunidade(BASE);
    expect(s.valor).toBeGreaterThanOrEqual(0);
    expect(s.valor).toBeLessThanOrEqual(100);
    expect(["excelente", "boa", "media", "baixa"]).toContain(s.classe);
    expect(s.desconto).toBe(50);
    expect(s.leilaoJaRealizado).toBe(false);
  });

  it("mais desconto não baixa o score", () => {
    const menos = calcularScoreOportunidade({ ...BASE, valor_leilao: 180000 });
    const mais = calcularScoreOportunidade({ ...BASE, valor_leilao: 60000 });
    expect(mais.valor).toBeGreaterThanOrEqual(menos.valor);
  });

  it("leilão passado é marcado como já realizado", () => {
    const s = calcularScoreOportunidade({ ...BASE, data_primeiro_leilao: "2020-01-01", data_segundo_leilao: "2020-01-10" });
    expect(s.leilaoJaRealizado).toBe(true);
  });

  it("detalhesDoScore junta a análise e as condições de compra conhecidas", () => {
    const d = detalhesDoScore({ ...BASE, ocupado: true, aceita_financiamento: false });
    expect(d.analise).toBeTruthy();
    expect(d.condicoesCompra).toEqual([
      { nome: "Ocupação", valor: "Ocupado" },
      { nome: "Financiamento", valor: "Não aceita" },
    ]);
  });

  it("avisa quando falta a localização", () => {
    const textos = alertasDoImovel({ ...BASE, cidade: null }).map((a) => a.texto);
    expect(textos).toContain("Localização incompleta");
  });
});

describe("fotos", () => {
  it("junta imagens, fotos e imagem, sem repetidos nem endereços inválidos", () => {
    const fotos = fotosDoImovel({
      imagens: ["https://x/a.jpg", ["https://x/b.jpg"]],
      fotos: ["https://x/a.jpg", "ftp://x/c.jpg"],
      imagem: " https://x/d.jpg ",
    });
    expect(fotos).toEqual(["https://x/a.jpg", "https://x/b.jpg", "https://x/d.jpg"]);
    expect(fotosDoImovel(null)).toEqual([]);
  });
});
