import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL } from "./api";
import { expiraEm, vigiarSessao } from "./sessao";

function jwt(payload) {
  const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${b64({ alg: "HS256", typ: "JWT" })}.${b64(payload)}.assinatura`;
}

function resposta(status) {
  return { ok: status < 400, status, json: async () => ({}) };
}

describe("expiraEm", () => {
  it("lê o exp do token", () => {
    expect(expiraEm(jwt({ sub: "1", exp: 2000000000 }))).toBe(2000000000 * 1000);
  });
  it("token sem exp ou estragado dá null", () => {
    expect(expiraEm(jwt({ sub: "1" }))).toBeNull();
    expect(expiraEm("tok")).toBeNull();
  });
});

describe("vigiarSessao", () => {
  let parar;
  beforeEach(() => vi.stubGlobal("fetch", vi.fn()));
  afterEach(() => {
    parar?.();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("401 num pedido com sessão à API avisa uma só vez", async () => {
    const aoExpirar = vi.fn();
    fetch.mockResolvedValue(resposta(401));
    parar = vigiarSessao("tok", aoExpirar);

    await window.fetch(`${API_URL}/alertas`, { headers: { Authorization: "Bearer tok" } });
    await window.fetch(`${API_URL}/alertas/email`, { headers: { Authorization: "Bearer tok" } });

    expect(aoExpirar).toHaveBeenCalledTimes(1);
  });

  it("401 sem sessão (ex.: senha errada no login) não conta", async () => {
    const aoExpirar = vi.fn();
    fetch.mockResolvedValue(resposta(401));
    parar = vigiarSessao("tok", aoExpirar);

    await window.fetch(`${API_URL}/login`, { method: "POST", headers: { "Content-Type": "application/json" } });
    await window.fetch("https://outro.site/x", { headers: { Authorization: "Bearer tok" } });

    expect(aoExpirar).not.toHaveBeenCalled();
  });

  it("avisa à hora em que o token expira e desligar repõe o fetch", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-04T10:00:00Z"));
    const aoExpirar = vi.fn();
    const original = window.fetch;
    const token = jwt({ sub: "1", exp: Date.parse("2026-11-04T11:00:00Z") / 1000 });

    parar = vigiarSessao(token, aoExpirar);
    expect(window.fetch).not.toBe(original);
    vi.advanceTimersByTime(59 * 60 * 1000);
    expect(aoExpirar).not.toHaveBeenCalled();
    vi.advanceTimersByTime(60 * 1000);
    expect(aoExpirar).toHaveBeenCalledTimes(1);

    parar();
    parar = null;
    expect(window.fetch).toBe(original);
  });
});
