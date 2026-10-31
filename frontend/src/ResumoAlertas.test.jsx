import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import ResumoPorEmail from "./componentes/ResumoPorEmail";
import DesligarAlertas from "./DesligarAlertas";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  localStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("Resumo por e-mail nos Alertas", () => {
  it("mostra a preferência e desliga ao desmarcar", async () => {
    const user = userEvent.setup();
    fetch
      .mockResolvedValueOnce(resposta(200, { ativo: true, envio_configurado: true }))
      .mockResolvedValueOnce(resposta(200, { ativo: false, envio_configurado: true }));
    render(<ResumoPorEmail token="tok" />);

    const caixa = await screen.findByRole("checkbox", { name: /resumo diário por e-mail/ });
    expect(caixa).toBeChecked();
    await user.click(caixa);

    await waitFor(() => expect(caixa).not.toBeChecked());
    const [url, opcoes] = fetch.mock.calls[1];
    expect(url).toMatch(/\/alertas\/email$/);
    expect(opcoes.method).toBe("PUT");
    expect(JSON.parse(opcoes.body)).toEqual({ ativo: false });
    expect(opcoes.headers.Authorization).toBe("Bearer tok");
  });

  it("avisa quando o envio ainda não está ligado no servidor", async () => {
    fetch.mockResolvedValueOnce(resposta(200, { ativo: true, envio_configurado: false }));
    render(<ResumoPorEmail token="tok" />);
    expect(await screen.findByText(/ainda não está ligado/)).toBeInTheDocument();
  });

  it("se a API falhar, o interruptor não aparece", async () => {
    fetch.mockResolvedValueOnce(resposta(500, {}));
    render(<ResumoPorEmail token="tok" />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});

describe("Ligação para deixar de receber", () => {
  it("desliga com o token da ligação e mostra a confirmação", async () => {
    fetch.mockResolvedValueOnce(resposta(200, { mensagem: "Deixou de receber os resumos." }));
    render(<DesligarAlertas token="token-da-ligacao-123" onConcluido={() => {}} />);

    expect(await screen.findByRole("status")).toHaveTextContent("Deixou de receber");
    const [url, opcoes] = fetch.mock.calls[0];
    expect(url).toMatch(/\/alertas\/email\/desligar$/);
    expect(JSON.parse(opcoes.body)).toEqual({ token: "token-da-ligacao-123" });
  });

  it("ligação inválida mostra o erro", async () => {
    fetch.mockResolvedValueOnce(resposta(400, { detail: "Ligação inválida." }));
    render(<DesligarAlertas token="token-errado-123456" onConcluido={() => {}} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Ligação inválida.");
  });

  it("a rota abre sem sessão e volta ao site", async () => {
    const user = userEvent.setup();
    fetch.mockImplementation(async (url) =>
      String(url).includes("/alertas/email/desligar")
        ? resposta(200, { mensagem: "Deixou de receber os resumos." })
        : resposta(200, []));
    render(
      <MemoryRouter initialEntries={["/desligar-alertas?token=abc123abc123abc123"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("status")).toHaveTextContent("Deixou de receber");
    await user.click(screen.getByRole("button", { name: "Ir para o site" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument());
  });
});
