import { afterEach, describe, expect, it, vi } from "vitest";
import { API_URL, ErroApi, mensagemDeErro, pedirApi } from "./api";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

afterEach(() => vi.unstubAllGlobals());

describe("pedirApi", () => {
  it("junta o endereço, o token e o corpo em JSON", async () => {
    const fetchFalso = vi.fn().mockResolvedValue(resposta(200, { ok: 1 }));
    vi.stubGlobal("fetch", fetchFalso);

    const dados = await pedirApi("/registo", { metodo: "POST", corpo: { a: 1 }, token: "t" });

    expect(dados).toEqual({ ok: 1 });
    const [url, opcoes] = fetchFalso.mock.calls[0];
    expect(url).toBe(`${API_URL}/registo`);
    expect(opcoes.method).toBe("POST");
    expect(opcoes.headers).toEqual({ "Content-Type": "application/json", Authorization: "Bearer t" });
    expect(JSON.parse(opcoes.body)).toEqual({ a: 1 });
  });

  it("sem corpo nem token não manda cabeçalhos", async () => {
    const fetchFalso = vi.fn().mockResolvedValue(resposta(200, []));
    vi.stubGlobal("fetch", fetchFalso);
    await pedirApi("/imoveis/1");
    expect(fetchFalso.mock.calls[0][1].headers).toEqual({});
    expect(fetchFalso.mock.calls[0][1].body).toBeUndefined();
  });

  it("erro HTTP lança ErroApi com a mensagem da API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(resposta(409, { detail: "Já existe." })));
    const erro = await pedirApi("/x").catch((e) => e);
    expect(erro).toBeInstanceOf(ErroApi);
    expect(erro.message).toBe("Já existe.");
    expect(erro.status).toBe(409);
  });

  it("erro sem JSON usa a mensagem por omissão", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 502, json: async () => { throw new Error("html"); } }));
    await expect(pedirApi("/x", { erroPadrao: "Falhou." })).rejects.toThrow("Falhou.");
  });
});

describe("mensagemDeErro", () => {
  it("lê o detail de texto e o da validação", () => {
    expect(mensagemDeErro({ detail: "x" }, "p")).toBe("x");
    expect(mensagemDeErro({ detail: [{ msg: "Value error, CRECI inválido." }] }, "p")).toBe("CRECI inválido.");
    expect(mensagemDeErro(null, "p")).toBe("p");
  });
});
