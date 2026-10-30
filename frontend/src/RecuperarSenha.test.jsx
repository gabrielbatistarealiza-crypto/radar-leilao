import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import Login from "./Login";
import { RedefinirSenha } from "./RecuperarSenha";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

const PEDIDO_OK = "Se o e-mail estiver registado, enviámos uma ligação para redefinir a senha.";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("Esqueci a senha", () => {
  it("pede a ligação com o e-mail já escrito no login", async () => {
    const user = userEvent.setup();
    fetch.mockResolvedValue(resposta(200, { mensagem: PEDIDO_OK }));
    render(<Login onLogin={() => {}} />);

    await user.type(screen.getByLabelText("E-mail"), "ana@teste.com");
    await user.click(screen.getByRole("button", { name: "Esqueci a senha" }));
    expect(screen.getByLabelText("E-mail")).toHaveValue("ana@teste.com");
    await user.click(screen.getByRole("button", { name: "Enviar ligação" }));

    expect(await screen.findByRole("status")).toHaveTextContent(PEDIDO_OK);
    const [url, opcoes] = fetch.mock.calls[0];
    expect(url).toMatch(/\/senha\/esquecida$/);
    expect(JSON.parse(opcoes.body)).toEqual({ email: "ana@teste.com" });

    await user.click(screen.getByRole("button", { name: "Voltar a entrar" }));
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });
});

describe("RedefinirSenha", () => {
  it("envia o código e a senha nova", async () => {
    const user = userEvent.setup();
    fetch.mockResolvedValue(resposta(200, { mensagem: "Senha alterada. Já pode entrar com a senha nova." }));
    render(<RedefinirSenha codigo="codigo-de-teste-123456789" onConcluido={() => {}} />);

    await user.type(screen.getByLabelText("Senha nova"), "novaSenha123");
    await user.type(screen.getByLabelText("Confirmar senha nova"), "novaSenha123");
    await user.click(screen.getByRole("button", { name: "Guardar senha" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Senha alterada");
    const [url, opcoes] = fetch.mock.calls[0];
    expect(url).toMatch(/\/senha\/redefinir$/);
    expect(JSON.parse(opcoes.body)).toEqual({ codigo: "codigo-de-teste-123456789", senha: "novaSenha123" });
  });

  it("não chama a API se as senhas não coincidem ou são curtas", async () => {
    const user = userEvent.setup();
    render(<RedefinirSenha codigo="codigo-de-teste-123456789" onConcluido={() => {}} />);

    await user.type(screen.getByLabelText("Senha nova"), "curta");
    await user.type(screen.getByLabelText("Confirmar senha nova"), "curta");
    await user.click(screen.getByRole("button", { name: "Guardar senha" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/8 caracteres/);

    await user.clear(screen.getByLabelText("Senha nova"));
    await user.type(screen.getByLabelText("Senha nova"), "novaSenha123");
    await user.click(screen.getByRole("button", { name: "Guardar senha" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/não coincidem/);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("mostra o erro da ligação expirada", async () => {
    const user = userEvent.setup();
    fetch.mockResolvedValue(resposta(400, { detail: "Ligação inválida ou expirada. Peça uma nova." }));
    render(<RedefinirSenha codigo="codigo-de-teste-123456789" onConcluido={() => {}} />);

    await user.type(screen.getByLabelText("Senha nova"), "novaSenha123");
    await user.type(screen.getByLabelText("Confirmar senha nova"), "novaSenha123");
    await user.click(screen.getByRole("button", { name: "Guardar senha" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("inválida ou expirada");
  });

  it("a ligação abre a página sem sessão e volta à entrada no fim", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/redefinir-senha?codigo=abc123abc123abc123abc123"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText("Escolher uma senha nova")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ir para a entrada" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument());
  });

  it("sem código avisa que a ligação está incompleta", () => {
    render(<RedefinirSenha codigo="" onConcluido={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Ligação incompleta");
  });
});
