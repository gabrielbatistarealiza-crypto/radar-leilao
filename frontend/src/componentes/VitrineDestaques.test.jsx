import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Login from "../Login";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

const DESTAQUE = {
  id: 11410, tipo: "Apartamento", cidade: "NOVA IGUACU", estado: "RJ",
  foto: "https://venda-imoveis.caixa.gov.br/fotos/F1.jpg",
  valor_avaliacao: 156374.33, valor_lance: 93824.59, desconto: 40, proximo_leilao: "2026-12-04",
};

function apiFalsa({ destaques = [DESTAQUE], anuncios = [] } = {}) {
  return vi.fn(async (url) => {
    if (String(url).includes("/imoveis/destaques")) return resposta(200, destaques);
    if (String(url).includes("/anuncios-imoveis/publicados")) return resposta(200, anuncios);
    return resposta(404, {});
  });
}

beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("Vitrine no ecrã de entrada", () => {
  it("mostra os imóveis em destaque com desconto e lance mínimo", async () => {
    vi.stubGlobal("fetch", apiFalsa());
    render(<Login onLogin={() => {}} />);

    expect(await screen.findByText("Oportunidades em destaque")).toBeInTheDocument();
    expect(screen.getByText("-40%")).toBeInTheDocument();
    expect(screen.getByText(/Lance mínimo/)).toHaveTextContent("93.824,59");
    expect(screen.getByRole("img", { name: /Apartamento em NOVA IGUACU/ })).toHaveAttribute("src", DESTAQUE.foto);
    expect(screen.queryByText("Anúncios de corretores")).not.toBeInTheDocument();
  });

  it("ao escolher um imóvel pede para entrar e põe o cursor no e-mail", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", apiFalsa());
    render(<Login onLogin={() => {}} />);

    await user.click(await screen.findByRole("button", { name: /NOVA IGUACU: 40% abaixo/ }));

    expect(screen.getByRole("status")).toHaveTextContent(/crie uma conta/);
    expect(screen.getByLabelText("E-mail")).toHaveFocus();
  });

  it("mostra anúncios de corretores quando há publicados", async () => {
    vi.stubGlobal("fetch", apiFalsa({
      anuncios: [{ id: 1, titulo: "Casa com piscina", cidade: "Campinas", estado: "SP", valor_anunciado: 500000, desconto: 10, fotos: [] }],
    }));
    render(<Login onLogin={() => {}} />);

    expect(await screen.findByText("Anúncios de corretores")).toBeInTheDocument();
    expect(screen.getByText("Casa com piscina")).toBeInTheDocument();
  });

  it("se a API falhar, o login continua e a vitrine não aparece", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("sem rede"); }));
    render(<Login onLogin={() => {}} />);

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByText("Oportunidades em destaque")).not.toBeInTheDocument();
  });
});
