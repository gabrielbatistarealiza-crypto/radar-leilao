import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("./imagens", async (original) => ({
  ...(await original()),
  reduzirImagem: vi.fn(async () => "data:image/jpeg;base64,/9j/AAAA"),
}));

import MeusAnuncios from "./MeusAnuncios";
import { API_URL } from "./api";
import { reduzirImagem, urlDaFoto } from "./imagens";

function resposta(status, corpo) {
  return { ok: status < 400, status, json: async () => corpo };
}

const ANUNCIO = {
  id: 7, titulo: "Casa", valor_mercado: 100000, valor_anunciado: 90000, status: "em_analise", fotos: [],
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  URL.createObjectURL = vi.fn(() => "blob:previa");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("urlDaFoto", () => {
  it("fotos carregadas usam o endereço da API; links ficam iguais", () => {
    expect(urlDaFoto("/anuncios-imoveis/fotos/abc")).toBe(`${API_URL}/anuncios-imoveis/fotos/abc`);
    expect(urlDaFoto("https://x/y.jpg")).toBe("https://x/y.jpg");
    expect(urlDaFoto(undefined)).toBeNull();
  });
});

describe("Fotos em Meus anúncios", () => {
  it("escolhe fotos no aparelho, reduz e envia cada uma depois de criar o anúncio", async () => {
    const user = userEvent.setup();
    fetch
      .mockResolvedValueOnce(resposta(200, []))                                   // lista
      .mockResolvedValueOnce(resposta(201, ANUNCIO))                              // criar
      .mockResolvedValueOnce(resposta(201, { id: 1, url: "/anuncios-imoveis/fotos/a" }))
      .mockResolvedValueOnce(resposta(201, { id: 2, url: "/anuncios-imoveis/fotos/b" }))
      .mockResolvedValueOnce(resposta(200, [{ ...ANUNCIO, fotos: [{ id: 1, url: "/anuncios-imoveis/fotos/a" }] }]));
    render(<MeusAnuncios token="tok" />);

    await user.click(await screen.findByRole("button", { name: "Anunciar imóvel" }));
    await user.type(screen.getByLabelText("Título"), "Casa");
    await user.type(screen.getByLabelText("Valor de mercado (R$)"), "100000");
    await user.type(screen.getByLabelText("Valor pedido (R$)"), "90000");
    const fotos = [new File(["a"], "sala.jpg", { type: "image/jpeg" }), new File(["b"], "quarto.png", { type: "image/png" })];
    await user.upload(screen.getByLabelText("Adicionar fotos"), fotos);
    expect(screen.getByText("Fotos (2 de 10)")).toBeInTheDocument();
    expect(screen.getByAltText("Foto nova: sala.jpg")).toHaveAttribute("src", "blob:previa");

    await user.click(screen.getByLabelText(/Aceito pagar/));
    await user.click(screen.getByRole("button", { name: "Enviar para aprovação" }));

    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/em análise/));
    expect(reduzirImagem).toHaveBeenCalledTimes(2);
    const envios = fetch.mock.calls.filter(([url]) => String(url).endsWith("/anuncios-imoveis/7/fotos/carregar"));
    expect(envios).toHaveLength(2);
    expect(JSON.parse(envios[0][1].body)).toEqual({ conteudo_base64: "data:image/jpeg;base64,/9j/AAAA" });
    // a capa aparece na lista
    expect(await screen.findByText(/1 foto\(s\)/)).toBeInTheDocument();
  });

  it("remover uma foto escolhida antes de enviar", async () => {
    const user = userEvent.setup();
    fetch.mockResolvedValueOnce(resposta(200, []));
    render(<MeusAnuncios token="tok" />);
    await user.click(await screen.findByRole("button", { name: "Anunciar imóvel" }));
    await user.upload(screen.getByLabelText("Adicionar fotos"), [new File(["a"], "sala.jpg", { type: "image/jpeg" })]);
    await user.click(screen.getByRole("button", { name: "Remover sala.jpg" }));
    expect(screen.getByText("Fotos (0 de 10)")).toBeInTheDocument();
  });

  it("ao editar, remover uma foto existente pede para a apagar ao salvar", async () => {
    const user = userEvent.setup();
    const comFoto = { ...ANUNCIO, fotos: [{ id: 5, url: "/anuncios-imoveis/fotos/x" }] };
    fetch
      .mockResolvedValueOnce(resposta(200, [comFoto]))
      .mockResolvedValueOnce(resposta(200, comFoto))   // PUT
      .mockResolvedValueOnce(resposta(204, null))      // DELETE foto
      .mockResolvedValueOnce(resposta(200, [ANUNCIO]));
    render(<MeusAnuncios token="tok" />);

    await user.click(await screen.findByRole("button", { name: "Editar Casa" }));
    expect(screen.getByAltText("Foto do anúncio")).toHaveAttribute("src", `${API_URL}/anuncios-imoveis/fotos/x`);
    await user.click(screen.getByRole("button", { name: "Remover foto" }));
    await user.click(screen.getByRole("button", { name: "Salvar alterações" }));

    await waitFor(() =>
      expect(fetch.mock.calls.some(([url, o]) => String(url).endsWith("/anuncios-imoveis/7/fotos/5") && o.method === "DELETE")).toBe(true));
  });

  it("não deixa passar de 10 fotos", async () => {
    const user = userEvent.setup();
    fetch.mockResolvedValueOnce(resposta(200, []));
    render(<MeusAnuncios token="tok" />);
    await user.click(await screen.findByRole("button", { name: "Anunciar imóvel" }));
    const muitas = Array.from({ length: 12 }, (_, i) => new File(["x"], `f${i}.jpg`, { type: "image/jpeg" }));
    await user.upload(screen.getByLabelText("Adicionar fotos"), muitas);
    expect(screen.getByText("Fotos (10 de 10)")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("no máximo 10 fotos");
    expect(screen.queryByLabelText("Adicionar fotos")).not.toBeInTheDocument();
  });
});
