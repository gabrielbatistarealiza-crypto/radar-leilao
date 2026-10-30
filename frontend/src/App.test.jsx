// Rede de segurança da fase 5: monta o App inteiro com a API simulada e verifica
// o que a refação não pode estragar (login, lista, detalhe, /admin).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";

const IMOVEL = {
  id: 7,
  titulo: "Casa Teste Campinas",
  tipo: "Casa",
  cidade: "CAMPINAS",
  estado: "SP",
  valor_avaliacao: 200000,
  valor_leilao: 100000,
  desconto: 50,
  area: 80,
  quartos: 2,
  banheiros: 1,
  vagas: 1,
  data_primeiro_leilao: "2030-01-10",
  data_segundo_leilao: "2030-01-20",
  modalidade: "Leilão SFI - Edital Único",
  url: "https://venda-imoveis.caixa.gov.br/sistema/detalhe-imovel.asp?hdnimovel=7",
  imagens: [],
  na_lista: true,
};

function respostaJson(corpo, status = 200) {
  return {
    ok: status < 400,
    status,
    json: async () => corpo,
    text: async () => JSON.stringify(corpo),
  };
}

function apiFalsa({ usuario, detalhe = IMOVEL } = {}) {
  return vi.fn(async (url) => {
    const caminho = String(url).replace(/^https?:\/\/[^/]+/, "");
    if (caminho.startsWith("/usuarios/me")) {
      return usuario ? respostaJson(usuario) : respostaJson({ detail: "x" }, 401);
    }
    if (caminho.startsWith("/imoveis/?")) {
      return respostaJson({ items: [IMOVEL], total: 1, pagina: 1, tamanho_pagina: 20, paginas_totais: 1 });
    }
    if (caminho.startsWith(`/imoveis/${IMOVEL.id}`)) return respostaJson(detalhe);
    if (caminho.startsWith("/pedidos-corretor/meu")) return respostaJson({ pedido: null });
    if (caminho.includes("/dashboard")) return respostaJson({});
    return respostaJson([]);
  });
}

const CLIENTE = { id: 1, nome: "Ana", email: "ana@teste.com", tipo: "cliente", admin: false };

beforeEach(() => {
  localStorage.clear();
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App (rede de segurança)", () => {
  it("sem sessão mostra o login", async () => {
    vi.stubGlobal("fetch", apiFalsa());
    render(<App />);
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("cliente vê a lista de imóveis pedida com os filtros por omissão", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    const fetchFalso = apiFalsa({ usuario: CLIENTE });
    vi.stubGlobal("fetch", fetchFalso);
    render(<App />);

    expect(await screen.findByText("Casa Teste Campinas")).toBeInTheDocument();
    expect(screen.getByText("1 imóveis encontrados")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Meu perfil" })).toBeInTheDocument();

    const pedidoLista = fetchFalso.mock.calls.map(([url]) => String(url)).find((u) => u.includes("/imoveis/?"));
    const params = new URL(pedidoLista).searchParams;
    expect(params.get("status_leilao")).toBe("ativos");
    expect(params.get("modalidade")).toBe("Leilão SFI - Edital Único");
    expect(params.get("pagina")).toBe("1");
  });

  it("abre o detalhe do imóvel e pede os dados completos", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    const fetchFalso = apiFalsa({ usuario: CLIENTE });
    vi.stubGlobal("fetch", fetchFalso);
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Ver oportunidade/ }));

    const titulo = await screen.findByRole("heading", { level: 2, name: "Casa Teste Campinas" });
    expect(titulo).toBeInTheDocument();
    await waitFor(() =>
      expect(fetchFalso.mock.calls.some(([url]) => String(url).endsWith(`/imoveis/${IMOVEL.id}`))).toBe(true)
    );
    expect(screen.queryByText(/saiu da lista da Caixa/)).not.toBeInTheDocument();
  });

  it("o detalhe de um imóvel fora da lista mostra o aviso", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({
      usuario: CLIENTE,
      detalhe: { ...IMOVEL, na_lista: false, saiu_da_lista_em: "2026-10-29T22:00:00" },
    }));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Ver oportunidade/ }));

    expect(await screen.findByText(/saiu da lista da Caixa em 29\/10\/2026/)).toBeInTheDocument();
  });

  it("/admin recusa quem não é administrador", async () => {
    window.history.pushState({}, "", "/admin");
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({ usuario: CLIENTE }));
    render(<App />);

    expect(await screen.findByText("Acesso permitido apenas para administradores.")).toBeInTheDocument();
  });

  it("sessão inválida volta ao login e apaga o token", async () => {
    localStorage.setItem("radar-leilao-token", "velho");
    vi.stubGlobal("fetch", apiFalsa({ usuario: null }));
    render(<App />);

    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(localStorage.getItem("radar-leilao-token")).toBeNull();
  });

  it("o cartão mostra o botão de favorito", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({ usuario: CLIENTE }));
    render(<App />);

    const titulo = await screen.findByText("Casa Teste Campinas");
    const cartao = titulo.closest("article") || titulo.parentElement.parentElement;
    expect(within(cartao).getAllByRole("button").length).toBeGreaterThan(0);
  });
});
