import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MeusAnuncios from "./MeusAnuncios";
import AnunciosPublicos from "./AnunciosPublicos";
import ModeracaoAnuncios from "./ModeracaoAnuncios";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

const ANUNCIO = {
  id: 7, usuario_id: 1, titulo: "Casa em Campinas", cidade: "Campinas", estado: "SP",
  valor_mercado: 300000, valor_anunciado: 285000, desconto: 5, fotos: [], status: "em_analise",
};

beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Meus anúncios", () => {
  it("publicar exige aceitar a comissão de 6% e envia para aprovação", async () => {
    const user = userEvent.setup();
    fetch
      .mockResolvedValueOnce(resposta(200, []))                       // lista inicial
      .mockResolvedValueOnce(resposta(201, ANUNCIO))                  // criar
      .mockResolvedValueOnce(resposta(200, [ANUNCIO]));               // lista depois
    render(<MeusAnuncios token="tok" />);

    await user.click(await screen.findByRole("button", { name: "Anunciar imóvel" }));
    await user.type(screen.getByLabelText("Título"), "Casa em Campinas");
    await user.type(screen.getByLabelText("Valor de mercado (R$)"), "300000");
    await user.type(screen.getByLabelText("Valor pedido (R$)"), "285000");
    expect(screen.getByText(/5,0% abaixo do valor de mercado/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Enviar para aprovação" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/comissão de 6%/);
    expect(fetch).toHaveBeenCalledTimes(1);

    await user.click(screen.getByLabelText(/Aceito pagar ao Radar Leilão uma comissão de 6%/));
    await user.click(screen.getByRole("button", { name: "Enviar para aprovação" }));

    expect(await screen.findByRole("status")).toHaveTextContent(/em análise/);
    const [url, opcoes] = fetch.mock.calls[1];
    expect(url).toMatch(/\/anuncios-imoveis$/);
    expect(JSON.parse(opcoes.body)).toMatchObject({ titulo: "Casa em Campinas", valor_anunciado: 285000, aceito_comissao: true });
    expect(await screen.findByText("Em análise")).toBeInTheDocument();
  });

  it("mostra o motivo de um anúncio rejeitado", async () => {
    fetch.mockResolvedValueOnce(resposta(200, [{ ...ANUNCIO, status: "rejeitado", motivo_rejeicao: "Faltam fotos" }]));
    render(<MeusAnuncios token="tok" />);
    expect(await screen.findByText("Rejeitado")).toBeInTheDocument();
    expect(screen.getByText(/Motivo: Faltam fotos/)).toBeInTheDocument();
  });
});

describe("Imóveis anunciados", () => {
  it("cliente demonstra interesse num anúncio publicado", async () => {
    const user = userEvent.setup();
    fetch
      .mockResolvedValueOnce(resposta(200, [{ ...ANUNCIO, status: "publicado" }]))
      .mockResolvedValueOnce(resposta(201, { id: 1 }));
    render(<AnunciosPublicos usuario={{ id: 2, tipo: "cliente" }} token="tok" />);

    await user.click(await screen.findByRole("button", { name: "Tenho interesse" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Interesse registrado");
    expect(fetch.mock.calls[1][0]).toMatch(/\/oportunidades\/anuncio\/7\/interesse$/);
  });

  it("o próprio anúncio não tem 'Tenho interesse' e o selo arredonda para baixo", async () => {
    fetch.mockResolvedValueOnce(resposta(200, [
      { ...ANUNCIO, status: "publicado", desconto: 99.6, e_meu: true },
    ]));
    render(<AnunciosPublicos usuario={{ id: 1, tipo: "cliente" }} token="tok" />);

    expect(await screen.findByText("Este anúncio é seu.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tenho interesse" })).not.toBeInTheDocument();
    expect(screen.getByText("-99%")).toBeInTheDocument();
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer tok");
  });

  it("sem anúncios publicados a secção não aparece", async () => {
    fetch.mockResolvedValueOnce(resposta(200, []));
    const { container } = render(<AnunciosPublicos usuario={{ id: 2, tipo: "cliente" }} token="tok" />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Moderação de anúncios", () => {
  it("aprova e rejeita com motivo", async () => {
    const user = userEvent.setup();
    const outro = { ...ANUNCIO, id: 8, titulo: "Apartamento" };
    fetch
      .mockResolvedValueOnce(resposta(200, [
        { ...ANUNCIO, dono: { nome: "Ana", email: "ana@t.com", tipo: "cliente" }, comissao_percentual: 6 },
        outro,
      ]))
      .mockResolvedValueOnce(resposta(200, { ...ANUNCIO, status: "publicado" }))
      .mockResolvedValueOnce(resposta(200, { ...outro, status: "rejeitado" }));
    vi.spyOn(window, "prompt").mockReturnValue("Faltam fotos");
    render(<ModeracaoAnuncios token="tok" />);

    expect(await screen.findByText(/Anunciante: Ana/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Aprovar" })[0]);
    await waitFor(() => expect(screen.queryByText("Casa em Campinas")).not.toBeInTheDocument());
    expect(fetch.mock.calls[1][0]).toMatch(/\/anuncios-imoveis\/7\/aprovar$/);

    await user.click(screen.getByRole("button", { name: "Rejeitar" }));
    await waitFor(() => expect(screen.getByText("Nenhum anúncio à espera de aprovação.")).toBeInTheDocument());
    expect(fetch.mock.calls[2][0]).toMatch(/\/anuncios-imoveis\/8\/rejeitar$/);
    expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ motivo: "Faltam fotos" });
  });
});
