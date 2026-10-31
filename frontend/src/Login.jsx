import { useRef, useState } from "react";

import Registo from "./Registo";
import { EsqueciSenha } from "./RecuperarSenha";
import VitrineDestaques from "./componentes/VitrineDestaques";

import { API_URL } from "./api";

function Login({ onLogin }) {
  const [criandoConta, setCriandoConta] = useState(false);
  const [esqueceuSenha, setEsqueceuSenha] = useState(false);
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [aviso, setAviso] = useState("");
  const campoEmail = useRef(null);

  // Um imóvel da vitrine: os detalhes pedem conta.
  const escolherDaVitrine = () => {
    setAviso("Entre ou crie uma conta grátis para ver a análise completa deste imóvel.");
    campoEmail.current?.focus();
    campoEmail.current?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  };

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
        // 422 = a API recusou o formato (detail é uma lista, que antes aparecia
        // como "[object Object]"); os outros erros trazem detail em texto.
        throw new Error(
          typeof dados.detail === "string"
            ? dados.detail
            : resposta.status === 422
              ? "Verifique o e-mail indicado."
              : "E-mail ou senha inválidos."
        );
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

  if (criandoConta) {
    return (
      <Registo
        onRegistado={(token) => onLogin(token)}
        onVoltar={() => setCriandoConta(false)}
      />
    );
  }

  if (esqueceuSenha) {
    return <EsqueciSenha emailInicial={email} onVoltar={() => setEsqueceuSenha(false)} />;
  }

  return (
    <div className="login-page login-com-vitrine">
      <div className="login-card">
        <h1>Radar Leilão</h1>
        <p className="login-slogan">Imóveis da Caixa abaixo da avaliação, com datas e descontos atualizados.</p>
        <p>Entre na sua conta</p>

        {aviso && <div className="login-ok" role="status">{aviso}</div>}

        <form onSubmit={entrar}>
          <label>
            E-mail
            <input
              ref={campoEmail}
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

        <button type="button" className="login-alternar" onClick={() => setCriandoConta(true)}>
          Não tem conta? Criar conta
        </button>

        <button type="button" className="login-alternar" onClick={() => setEsqueceuSenha(true)}>
          Esqueci a senha
        </button>
      </div>

      <VitrineDestaques onEscolher={escolherDaVitrine} />
    </div>
  );
}

export default Login;
