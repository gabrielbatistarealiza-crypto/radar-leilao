import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const entrar = async (e) => {
    e.preventDefault();

    setErro("");
    setCarregando(true);
    const controlador = new AbortController();
    const timeout = setTimeout(() => controlador.abort(), 20000);

    try {
      const resposta = await fetch(`${API_URL}/login`, {
        method: "POST",
        signal: controlador.signal,
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          senha,
        }),
      });

      const dados = await resposta.json().catch(() => ({}));

      if (!resposta.ok) {
        throw new Error(dados.detail || "E-mail ou senha inválidos.");
      }

      localStorage.setItem("radar-leilao-token", dados.access_token);

      onLogin(dados.access_token);
    } catch (error) {
      setErro(
        error.name === "AbortError"
          ? "A API demorou para responder. Verifique o terminal do backend e tente novamente."
          : error instanceof TypeError
            ? "Não foi possível conectar à API. Confira se o backend está ativo."
            : error.message
      );
    } finally {
      clearTimeout(timeout);
      setCarregando(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Radar Leilão</h1>
        <p>Entre na sua conta</p>

        <form onSubmit={entrar}>
          <label>
            E-mail
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="seu@email.com"
              required
            />
          </label>

          <label>
            Senha
            <input
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              placeholder="Sua senha"
              required
            />
          </label>

          {erro && <div className="login-error">{erro}</div>}

          <button type="submit" disabled={carregando}>
            {carregando ? "Entrando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default Login;
