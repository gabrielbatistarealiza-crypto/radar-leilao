import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "../App";
import ApagarConta from "./ApagarConta";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn());
});
afterEach(() => vi.unstubAllGlobals());

describe("Apagar a minha conta", () => {
  it("pede a senha, explica o que se perde e envia o pedido", async () => {
    const user = userEvent.setup();
    const onApagada = vi.fn();
    fetch.mockResolvedValue(resposta(200, { mensagem: "ok" }));
    render(<ApagarConta token="tok" onApagada={onApagada} />);

    await user.click(screen.getByRole("button", { name: "Apagar a minha conta" }));
    expect(screen.getByText(/Não dá para desfazer/)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Confirme com a sua senha"), "Senha#12345");
    await user.click(screen.getByRole("button", { name: "Apagar definitivamente" }));

    await waitFor(() => expect(onApagada).toHaveBeenCalled());
    const [url, opcoes] = fetch.mock.calls[0];
    expect(url).toMatch(/\/usuarios\/me\/apagar$/);
    expect(JSON.parse(opcoes.body)).toEqual({ senha: "Senha#12345" });
    expect(opcoes.headers.Authorization).toBe("Bearer tok");
  });

  it("senha errada mostra o erro e não sai", async () => {
    const user = userEvent.setup();
    const onApagada = vi.fn();
    fetch.mockResolvedValue(resposta(403, { detail: "Senha incorreta." }));
    render(<ApagarConta token="tok" onApagada={onApagada} />);

    await user.click(screen.getByRole("button", { name: "Apagar a minha conta" }));
    await user.type(screen.getByLabelText("Confirme com a sua senha"), "errada");
    await user.click(screen.getByRole("button", { name: "Apagar definitivamente" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Senha incorreta.");
    expect(onApagada).not.toHaveBeenCalled();
  });

  it("cancelar fecha sem pedir nada", async () => {
    const user = userEvent.setup();
    render(<ApagarConta token="tok" />);
    await user.click(screen.getByRole("button", { name: "Apagar a minha conta" }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.getByRole("button", { name: "Apagar a minha conta" })).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("no site: depois de apagar volta ao ecrã de entrada com a confirmação", async () => {
    const user = userEvent.setup();
    localStorage.setItem("radar-leilao-token", "tok");
    fetch.mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/usuarios/me/apagar")) return resposta(200, { mensagem: "ok" });
      if (u.includes("/usuarios/me")) return resposta(200, { id: 1, nome: "Ana", email: "a@t.com", tipo: "cliente", admin: false });
      if (u.includes("/imoveis/?")) return resposta(200, { items: [], total: 0, pagina: 1, tamanho_pagina: 20, paginas_totais: 1 });
      if (u.includes("/pedidos-corretor/meu")) return resposta(200, { pedido: null });
      return resposta(200, []);
    });
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    await user.click(await screen.findByRole("button", { name: "Apagar a minha conta" }));
    await user.type(screen.getByLabelText("Confirme com a sua senha"), "Senha#12345");
    await user.click(screen.getByRole("button", { name: "Apagar definitivamente" }));

    expect(await screen.findByText("A sua conta e os seus dados foram apagados.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(localStorage.getItem("radar-leilao-token")).toBeNull();
  });
});
