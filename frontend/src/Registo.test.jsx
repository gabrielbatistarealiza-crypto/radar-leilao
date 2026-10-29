import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Login from "./Login";
import Registo, { mensagemDeErro, validarRegisto } from "./Registo";
import PedidosCorretorAdmin, { textoConfirmacaoAprovar } from "./PedidosCorretorAdmin";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

const valido = {
  nome: "Ana", email: "ana@teste.com", senha: "segura123", confirmacao: "segura123",
  souCorretor: false, creci: "",
};

describe("validarRegisto", () => {
  it("aceita um formulário completo", () => {
    expect(validarRegisto(valido)).toBe("");
  });

  it.each([
    [{ nome: " " }, /nome/],
    [{ email: "ana" }, /e-mail/],
    [{ senha: "curta", confirmacao: "curta" }, /8 caracteres/],
    [{ confirmacao: "outra123" }, /não coincidem/],
    [{ souCorretor: true, creci: "CRECI" }, /CRECI/],
  ])("recusa %o", (mudanca, erro) => {
    expect(validarRegisto({ ...valido, ...mudanca })).toMatch(erro);
  });
});

describe("mensagemDeErro", () => {
  it("usa o texto da API ou a primeira mensagem de validação", () => {
    expect(mensagemDeErro({ detail: "E-mail repetido" }, "x")).toBe("E-mail repetido");
    expect(mensagemDeErro({ detail: [{ msg: "Value error, CRECI inválido." }] }, "x")).toBe("CRECI inválido.");
    expect(mensagemDeErro({}, "padrão")).toBe("padrão");
  });
});

describe("Registo", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    localStorage.clear();
  });
  afterEach(() => vi.unstubAllGlobals());

  async function preencher(user, extra = {}) {
    await user.type(screen.getByLabelText("Nome"), "Ana");
    await user.type(screen.getByLabelText("E-mail"), "ana@teste.com");
    await user.type(screen.getByLabelText("Senha"), "segura123");
    await user.type(screen.getByLabelText("Confirmar senha"), extra.confirmacao || "segura123");
  }

  it("envia o pedido de corretor junto e entra com o token devolvido", async () => {
    const user = userEvent.setup();
    const onRegistado = vi.fn();
    fetch.mockResolvedValue(resposta(201, { access_token: "tok", pedido_corretor: { status: "PENDENTE" } }));
    render(<Registo onRegistado={onRegistado} onVoltar={() => {}} />);

    await preencher(user);
    await user.click(screen.getByLabelText(/Sou corretor/));
    await user.type(screen.getByLabelText("CRECI"), "CRECI-SP 123");
    await user.click(screen.getByRole("button", { name: "Criar conta" }));

    await waitFor(() => expect(onRegistado).toHaveBeenCalledWith("tok", expect.anything()));
    const [url, opcoes] = fetch.mock.calls[0];
    expect(url).toMatch(/\/registo$/);
    const corpo = JSON.parse(opcoes.body);
    expect(corpo).toMatchObject({ nome: "Ana", email: "ana@teste.com", corretor: { creci: "CRECI-SP 123" } });
    expect(corpo).not.toHaveProperty("tipo");
    expect(localStorage.getItem("radar-leilao-token")).toBe("tok");
  });

  it("não chama a API quando as senhas não coincidem", async () => {
    const user = userEvent.setup();
    render(<Registo onRegistado={() => {}} onVoltar={() => {}} />);

    await preencher(user, { confirmacao: "diferente1" });
    await user.click(screen.getByRole("button", { name: "Criar conta" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/não coincidem/);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("mostra o erro da API", async () => {
    const user = userEvent.setup();
    fetch.mockResolvedValue(resposta(409, { detail: "Este e-mail já está cadastrado." }));
    render(<Registo onRegistado={() => {}} onVoltar={() => {}} />);

    await preencher(user);
    await user.click(screen.getByRole("button", { name: "Criar conta" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Este e-mail já está cadastrado.");
  });

  it("o ecrã de login abre e fecha o registo", async () => {
    const user = userEvent.setup();
    render(<Login onLogin={() => {}} />);

    await user.click(screen.getByRole("button", { name: /Criar conta/ }));
    expect(screen.getByLabelText("Confirmar senha")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Entrar/ }));
    expect(screen.queryByLabelText("Confirmar senha")).not.toBeInTheDocument();
  });
});

describe("PedidosCorretorAdmin", () => {
  const pedido = {
    id: 7, creci: "CRECI-SP 1", usuario: { nome: "Ana", email: "ana@teste.com" },
    oportunidades_como_cliente: 2,
  };

  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("avisa das oportunidades como cliente antes de aprovar", () => {
    expect(textoConfirmacaoAprovar(pedido)).toMatch(/2 oportunidades como cliente/);
    expect(textoConfirmacaoAprovar({ ...pedido, oportunidades_como_cliente: 0 })).not.toMatch(/Atenção/);
  });

  it("aprova depois de confirmar e tira o pedido da lista", async () => {
    const user = userEvent.setup();
    const onDecidido = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fetch
      .mockResolvedValueOnce(resposta(200, [pedido]))
      .mockResolvedValueOnce(resposta(200, { ...pedido, status: "APROVADO" }));
    render(<PedidosCorretorAdmin token="t" onDecidido={onDecidido} />);

    await user.click(await screen.findByRole("button", { name: "Aprovar" }));

    await waitFor(() => expect(onDecidido).toHaveBeenCalled());
    expect(fetch.mock.calls[1][0]).toMatch(/\/admin\/pedidos-corretor\/7\/aprovar$/);
    expect(screen.getByText("Nenhum pedido pendente.")).toBeInTheDocument();
  });

  it("não faz nada se o admin cancelar a confirmação", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    fetch.mockResolvedValueOnce(resposta(200, [pedido]));
    render(<PedidosCorretorAdmin token="t" />);

    await user.click(await screen.findByRole("button", { name: "Aprovar" }));

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/CRECI-SP 1/)).toBeInTheDocument();
  });

  it("rejeita com o motivo escrito", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue("CRECI inexistente");
    fetch
      .mockResolvedValueOnce(resposta(200, [pedido]))
      .mockResolvedValueOnce(resposta(200, { ...pedido, status: "REJEITADO" }));
    render(<PedidosCorretorAdmin token="t" />);

    await user.click(await screen.findByRole("button", { name: "Rejeitar" }));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(fetch.mock.calls[1][0]).toMatch(/\/7\/rejeitar$/);
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ motivo: "CRECI inexistente" });
  });
});
