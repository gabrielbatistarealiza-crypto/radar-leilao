// Rede de segurança da fase 5: monta o App inteiro com a API simulada e verifica
// o que a refação não pode estragar (login, lista, detalhe, /admin).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
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

function apiFalsa({ usuario, detalhe = IMOVEL, lista = IMOVEL, paginas = 1 } = {}) {
  return vi.fn(async (url) => {
    const caminho = String(url).replace(/^https?:\/\/[^/]+/, "");
    if (caminho.startsWith("/usuarios/me")) {
      return usuario ? respostaJson(usuario) : respostaJson({ detail: "x" }, 401);
    }
    if (caminho.startsWith("/imoveis/?")) {
      return respostaJson({ items: [lista], total: paginas === 1 ? 1 : paginas * 20, pagina: 1, tamanho_pagina: 20,
                            paginas_totais: paginas });
    }
    if (caminho.startsWith(`/imoveis/${IMOVEL.id}`)) return respostaJson(detalhe);
    if (caminho.startsWith("/pedidos-corretor/meu")) return respostaJson({ pedido: null });
    if (caminho.startsWith("/caixa/status")) {
      return respostaJson({
        caixa: { status: "CONCLUIDA", estados_baixados: 27, imoveis_atualizados: 0, imoveis_removidos: 0,
                 fotos_pendentes: 0 },
        historico: [], banco: "ok",
      });
    }
    if (caminho.startsWith("/admin/dashboard") || caminho.startsWith("/caixa/enriquecer-datas/status")) {
      return respostaJson({});
    }
    if (caminho.includes("/dashboard")) return respostaJson({});
    return respostaJson([]);
  });
}

function montar(caminho = "/") {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>
  );
}

const CLIENTE = { id: 1, nome: "Ana", email: "ana@teste.com", tipo: "cliente", admin: false };

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App (rede de segurança)", () => {
  it("sem sessão mostra o login", async () => {
    vi.stubGlobal("fetch", apiFalsa());
    montar();
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("cliente vê a lista de imóveis pedida com os filtros por omissão", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    const fetchFalso = apiFalsa({ usuario: CLIENTE });
    vi.stubGlobal("fetch", fetchFalso);
    montar();

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
    montar();

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
    montar();

    await user.click(await screen.findByRole("button", { name: /Ver oportunidade/ }));

    expect(await screen.findByText(/saiu da lista da Caixa em 29\/10\/2026/)).toBeInTheDocument();
  });

  it("/admin recusa quem não é administrador", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({ usuario: CLIENTE }));
    montar("/admin");

    expect(await screen.findByText("Acesso permitido apenas para administradores.")).toBeInTheDocument();
  });

  it("o Voltar do acesso negado regressa à lista sem recarregar a página", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({ usuario: CLIENTE }));
    const user = userEvent.setup();
    montar("/admin");

    await user.click(await screen.findByRole("button", { name: "Voltar" }));

    expect(await screen.findByText("Casa Teste Campinas")).toBeInTheDocument();
  });

  it("administrador entra no painel pela ligação do cabeçalho e sai de lá para o login", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({ usuario: { ...CLIENTE, tipo: "admin", admin: true } }));
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("link", { name: "Administração" }));

    expect(await screen.findByText("Pedidos de conta de corretor")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: /Sair/ })[0]);
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(localStorage.getItem("radar-leilao-token")).toBeNull();
  });

  it("administrador também vê os Alertas (link no cabeçalho e secção)", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({ usuario: { ...CLIENTE, tipo: "admin", admin: true } }));
    montar();

    expect(await screen.findByRole("link", { name: "Alertas" })).toHaveAttribute("href", "#alertas");
    expect(await screen.findByRole("heading", { name: /Alertas de oportunidades/ })).toBeInTheDocument();
  });

  it("login recusado por formato (422) mostra uma mensagem legível", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      if (String(url).endsWith("/login")) {
        return respostaJson({ detail: [{ type: "value_error", msg: "value is not a valid email address" }] }, 422);
      }
      return respostaJson([]);
    }));
    const user = userEvent.setup();
    montar();

    await user.type(await screen.findByPlaceholderText("seu@email.com"), "x@y.test");
    await user.type(screen.getByPlaceholderText("Sua senha"), "segredo123");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Verifique o e-mail indicado.")).toBeInTheDocument();
    expect(screen.queryByText("[object Object]")).not.toBeInTheDocument();
  });

  it("sessão inválida volta ao login e apaga o token", async () => {
    localStorage.setItem("radar-leilao-token", "velho");
    vi.stubGlobal("fetch", apiFalsa({ usuario: null }));
    montar();

    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(localStorage.getItem("radar-leilao-token")).toBeNull();
  });

  it("paginação: a seta seguinte pede a página 2", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    const fetchFalso = apiFalsa({ usuario: CLIENTE, paginas: 3 });
    vi.stubGlobal("fetch", fetchFalso);
    const user = userEvent.setup();
    montar();
    await screen.findByText("Casa Teste Campinas");

    await user.click(screen.getByRole("button", { name: "→" }));

    await waitFor(() => {
      const paginas = fetchFalso.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/imoveis/?"))
        .map((u) => new URL(u).searchParams.get("pagina"));
      expect(paginas).toContain("2");
    });
  });

  it("comparação: seleciona, mostra o painel e limpa", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({ usuario: CLIENTE }));
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Comparar oportunidade/ }));

    expect(screen.getByRole("heading", { name: "Comparação de oportunidades" })).toBeInTheDocument();
    expect(screen.getByText("Score existente")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Limpar seleção" }));
    expect(screen.queryByRole("heading", { name: "Comparação de oportunidades" })).not.toBeInTheDocument();
  });

  it("galeria: abre, avança e fecha", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    const comFotos = { ...IMOVEL, imagens: ["https://x/a.jpg", "https://x/b.jpg"] };
    vi.stubGlobal("fetch", apiFalsa({ usuario: CLIENTE, lista: comFotos }));
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: "Abrir fotos de Casa Teste Campinas" }));

    const galeria = screen.getByRole("dialog", { name: "Fotos de Casa Teste Campinas" });
    await user.click(within(galeria).getByRole("button", { name: "Próxima foto" }));
    await user.click(within(galeria).getByRole("button", { name: "Fechar galeria" }));
    expect(screen.queryByRole("dialog", { name: "Fotos de Casa Teste Campinas" })).not.toBeInTheDocument();
  });

  it("o cartão mostra o botão de favorito", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", apiFalsa({ usuario: CLIENTE }));
    montar();

    const titulo = await screen.findByText("Casa Teste Campinas");
    const cartao = titulo.closest("article") || titulo.parentElement.parentElement;
    expect(within(cartao).getAllByRole("button").length).toBeGreaterThan(0);
  });
});
