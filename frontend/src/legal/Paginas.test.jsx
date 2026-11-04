import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "../App";
import Login from "../Login";
import { EMAIL_CONTATO } from "./dados";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

function montar(caminho) {
  return render(
    <MemoryRouter initialEntries={[caminho]}>
      <App />
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async () => resposta(200, [])));
});
afterEach(() => vi.unstubAllGlobals());

describe("Política de Privacidade e Termos de Uso", () => {
  it("a política abre sem sessão e diz com quem partilhamos e como pedir os dados", async () => {
    montar("/privacidade");
    expect(screen.getByRole("heading", { level: 1, name: "Política de Privacidade" })).toBeInTheDocument();
    for (const fornecedor of ["Render", "Brevo", "Anthropic"]) {
      expect(screen.getAllByText(new RegExp(fornecedor)).length).toBeGreaterThan(0);
    }
    expect(screen.getByRole("heading", { name: /Os seus direitos/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: EMAIL_CONTATO })[0]).toHaveAttribute("href", `mailto:${EMAIL_CONTATO}`);
  });

  it("os termos abrem sem sessão e avisam que não há ligação à Caixa", async () => {
    const user = userEvent.setup();
    montar("/termos");
    expect(screen.getByRole("heading", { level: 1, name: "Termos de Uso" })).toBeInTheDocument();
    expect(screen.getByText(/não tem qualquer ligação com a Caixa/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Voltar ao site" }));
    expect(await screen.findByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("o ecrã de entrada e o registo levam às duas páginas", async () => {
    const user = userEvent.setup();
    render(<Login onLogin={() => {}} />);
    expect(screen.getByRole("link", { name: "Termos de Uso" })).toHaveAttribute("href", "/termos");
    expect(screen.getByRole("link", { name: "Política de Privacidade" })).toHaveAttribute("href", "/privacidade");

    await user.click(screen.getByRole("button", { name: /Criar conta/ }));
    expect(screen.getByText(/Ao criar a conta, você concorda/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Termos de Uso" })).toHaveAttribute("href", "/termos");
  });

  it("com sessão, o rodapé da página principal tem as duas ligações", async () => {
    localStorage.setItem("radar-leilao-token", "tok");
    vi.stubGlobal("fetch", vi.fn(async (url) => {
      const u = String(url);
      if (u.includes("/usuarios/me")) return resposta(200, { id: 1, nome: "Ana", email: "a@t.com", tipo: "cliente", admin: false });
      if (u.includes("/imoveis/?")) return resposta(200, { items: [], total: 0, pagina: 1, tamanho_pagina: 20, paginas_totais: 1 });
      if (u.includes("/pedidos-corretor/meu")) return resposta(200, { pedido: null });
      return resposta(200, []);
    }));
    montar("/");
    expect(await screen.findByRole("link", { name: "Política de Privacidade" })).toHaveAttribute("href", "/privacidade");
  });
});
