import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Consultoria, { perguntasSugeridas } from "./Consultoria";

function respostaOk(corpo) {
  return { ok: true, status: 200, json: async () => corpo };
}

function respostaErro(status, corpo) {
  return { ok: false, status, json: async () => corpo };
}

describe("perguntasSugeridas", () => {
  it("usa perguntas gerais quando não há imóvel", () => {
    const lista = perguntasSugeridas(null);
    expect(lista).toHaveLength(3);
    expect(lista[0]).toMatch(/judicial e extrajudicial/i);
  });

  it("sugere desocupação quando o imóvel está ocupado", () => {
    const lista = perguntasSugeridas({ ocupado: true });
    expect(lista[0]).toMatch(/desocupação/i);
  });

  it("sugere financiamento/FGTS quando o imóvel aceita", () => {
    expect(perguntasSugeridas({ aceita_fgts: true }).join(" ")).toMatch(/FGTS/);
    expect(perguntasSugeridas({ aceita_financiamento: true }).join(" ")).toMatch(
      /financiamento/
    );
  });

  it("não passa de 4 sugestões", () => {
    const lista = perguntasSugeridas({
      ocupado: true,
      aceita_fgts: true,
      modalidade: "Leilão judicial",
    });
    expect(lista.length).toBeLessThanOrEqual(4);
  });
});

describe("<Consultoria />", () => {
  let fetchMock;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("mostra o aviso legal e as sugestões iniciais", () => {
    render(<Consultoria token="abc" />);

    expect(screen.getByRole("note")).toHaveTextContent(/não substitui/i);
    expect(
      screen.getByRole("button", { name: /judicial e extrajudicial/i })
    ).toBeInTheDocument();
  });

  it("mantém o botão de enviar desabilitado com o campo vazio", async () => {
    const user = userEvent.setup();
    render(<Consultoria token="abc" />);

    const enviar = screen.getByRole("button", { name: /enviar pergunta/i });
    expect(enviar).toBeDisabled();

    await user.type(screen.getByLabelText(/sua pergunta/i), "   ");
    expect(enviar).toBeDisabled();

    await user.type(screen.getByLabelText(/sua pergunta/i), "Como funciona?");
    expect(enviar).toBeEnabled();
  });

  it("envia a pergunta com o token e mostra a resposta", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      respostaOk({ resposta: "O ITBI é municipal.", aviso: "Aviso do servidor." })
    );

    render(<Consultoria token="token-123" />);
    await user.type(screen.getByLabelText(/sua pergunta/i), "Quem cobra o ITBI?");
    await user.click(screen.getByRole("button", { name: /enviar pergunta/i }));

    expect(await screen.findByText("O ITBI é municipal.")).toBeInTheDocument();
    expect(screen.getByText("Quem cobra o ITBI?")).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Aviso do servidor.");

    const [url, opcoes] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/consultoria\/perguntar$/);
    expect(opcoes.method).toBe("POST");
    expect(opcoes.headers.Authorization).toBe("Bearer token-123");

    const corpo = JSON.parse(opcoes.body);
    expect(corpo.pergunta).toBe("Quem cobra o ITBI?");
    expect(corpo.historico).toEqual([]);
  });

  it("envia o histórico na segunda pergunta", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(respostaOk({ resposta: "Primeira resposta." }))
      .mockResolvedValueOnce(respostaOk({ resposta: "Segunda resposta." }));

    render(<Consultoria token="abc" />);
    const campo = screen.getByLabelText(/sua pergunta/i);

    await user.type(campo, "Primeira?");
    await user.click(screen.getByRole("button", { name: /enviar pergunta/i }));
    await screen.findByText("Primeira resposta.");

    await user.type(campo, "Segunda?");
    await user.click(screen.getByRole("button", { name: /enviar pergunta/i }));
    await screen.findByText("Segunda resposta.");

    const corpo = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(corpo.historico).toEqual([
      { role: "user", content: "Primeira?" },
      { role: "assistant", content: "Primeira resposta." },
    ]);
  });

  it("clicar numa sugestão envia a pergunta", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(respostaOk({ resposta: "Resposta da sugestão." }));

    render(<Consultoria token="abc" />);
    await user.click(
      screen.getByRole("button", { name: /quais custos existem/i })
    );

    expect(await screen.findByText("Resposta da sugestão.")).toBeInTheDocument();
    const corpo = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(corpo.pergunta).toMatch(/custos existem/i);
  });

  // Contrato da API: o pedido leva só `pergunta` e `historico`. O imóvel serve
  // para as sugestões no ecrã, mas não é enviado (a consultoria responde em
  // caráter geral; o backend também não usa esses dados).
  it("usa sugestões do imóvel sem enviar os dados do imóvel", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(respostaOk({ resposta: "ok" }));

    const imovel = {
      id: 7,
      titulo: "Casa em Campinas",
      ocupado: true,
      valor_leilao: 180000,
      campo_interno: "não deve ir",
    };

    render(<Consultoria token="abc" imovel={imovel} />);
    expect(screen.getByText(/Casa em Campinas/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /desocupação/i }));
    await screen.findByText("ok");

    const corpo = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(corpo).toEqual({
      pergunta: "Este imóvel está ocupado. Como funciona a desocupação?",
      historico: [],
    });
    expect(corpo).not.toHaveProperty("imovel");
    expect(JSON.stringify(corpo)).not.toContain("não deve ir");
  });

  it("mostra a mensagem de erro devolvida pela API", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      respostaErro(429, { detail: "Muitas perguntas em pouco tempo." })
    );

    render(<Consultoria token="abc" />);
    await user.type(screen.getByLabelText(/sua pergunta/i), "Oi?");
    await user.click(screen.getByRole("button", { name: /enviar pergunta/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Muitas perguntas em pouco tempo."
    );
  });

  it("mostra o erro quando a rede falha", async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new Error("Failed to fetch"));

    render(<Consultoria token="abc" />);
    await user.type(screen.getByLabelText(/sua pergunta/i), "Oi?");
    await user.click(screen.getByRole("button", { name: /enviar pergunta/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to fetch/i);
  });

  it("limpa o campo depois de enviar e reabilita o botão ao terminar", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(respostaOk({ resposta: "Pronto." }));

    render(<Consultoria token="abc" />);
    const campo = screen.getByLabelText(/sua pergunta/i);
    await user.type(campo, "Pergunta?");
    await user.click(screen.getByRole("button", { name: /enviar pergunta/i }));

    await screen.findByText("Pronto.");
    expect(campo).toHaveValue("");
    await waitFor(() => expect(campo).toBeEnabled());
  });

  it("Enter envia e Shift+Enter não envia", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(respostaOk({ resposta: "Enviada." }));

    render(<Consultoria token="abc" />);
    const campo = screen.getByLabelText(/sua pergunta/i);

    await user.type(campo, "Linha 1{Shift>}{Enter}{/Shift}Linha 2");
    expect(fetchMock).not.toHaveBeenCalled();

    await user.type(campo, "{Enter}");
    await screen.findByText("Enviada.");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("começa uma conversa nova ao trocar de imóvel", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(respostaOk({ resposta: "Resposta A." }));

    const { rerender } = render(
      <Consultoria token="abc" imovel={{ id: 1, titulo: "Imóvel A" }} />
    );
    await user.type(screen.getByLabelText(/sua pergunta/i), "Pergunta A?");
    await user.click(screen.getByRole("button", { name: /enviar pergunta/i }));
    await screen.findByText("Resposta A.");

    rerender(<Consultoria token="abc" imovel={{ id: 2, titulo: "Imóvel B" }} />);

    await waitFor(() =>
      expect(screen.queryByText("Resposta A.")).not.toBeInTheDocument()
    );
    expect(screen.getByText(/Imóvel B/)).toBeInTheDocument();
  });
});
