// Fase 4B: recuperar a senha por e-mail.
// EsqueciSenha pede a ligação; RedefinirSenha é a página aberta pela ligação
// (/redefinir-senha?codigo=...) e funciona sem sessão.
import { useState } from "react";

import { pedirApi } from "./api";

const SEM_LIGACAO = "Não foi possível conectar à API. Tente novamente daqui a pouco.";

function erroAmigavel(erro, padrao) {
  return erro instanceof TypeError ? SEM_LIGACAO : erro.message || padrao;
}

export function EsqueciSenha({ emailInicial = "", onVoltar }) {
  const [email, setEmail] = useState(emailInicial);
  const [enviado, setEnviado] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const pedir = async (e) => {
    e.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      const dados = await pedirApi("/senha/esquecida", {
        metodo: "POST",
        corpo: { email },
        erroPadrao: "Verifique o e-mail indicado.",
      });
      setEnviado(dados.mensagem);
    } catch (falha) {
      setErro(erroAmigavel(falha, "Não foi possível pedir a ligação."));
    } finally {
      setCarregando(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Radar Leilão</h1>
        <p>Recuperar a senha</p>

        {enviado ? (
          <div className="login-ok" role="status">
            {enviado} Veja também a pasta de spam. A ligação vale durante 1 hora.
          </div>
        ) : (
          <form onSubmit={pedir}>
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

            {erro && <div className="login-error" role="alert">{erro}</div>}

            <button type="submit" disabled={carregando}>
              {carregando ? "Enviando..." : "Enviar ligação"}
            </button>
          </form>
        )}

        <button type="button" className="login-alternar" onClick={onVoltar}>
          Voltar a entrar
        </button>
      </div>
    </div>
  );
}

export function RedefinirSenha({ codigo, onConcluido }) {
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [feito, setFeito] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const guardar = async (e) => {
    e.preventDefault();
    setErro("");
    if (senha.length < 8) return setErro("A senha precisa de pelo menos 8 caracteres.");
    if (senha !== confirmacao) return setErro("As senhas não coincidem.");

    setCarregando(true);
    try {
      const dados = await pedirApi("/senha/redefinir", {
        metodo: "POST",
        corpo: { codigo, senha },
        erroPadrao: "Ligação inválida ou expirada. Peça uma nova.",
      });
      setFeito(dados.mensagem);
    } catch (falha) {
      setErro(erroAmigavel(falha, "Não foi possível alterar a senha."));
    } finally {
      setCarregando(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Radar Leilão</h1>
        <p>Escolher uma senha nova</p>

        {!codigo ? (
          <div className="login-error" role="alert">
            Ligação incompleta. Abra a ligação do e-mail ou peça uma nova.
          </div>
        ) : feito ? (
          <div className="login-ok" role="status">{feito}</div>
        ) : (
          <form onSubmit={guardar}>
            <label>
              Senha nova
              <input
                type="password"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>
            <label>
              Confirmar senha nova
              <input
                type="password"
                value={confirmacao}
                onChange={(e) => setConfirmacao(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>

            {erro && <div className="login-error" role="alert">{erro}</div>}

            <button type="submit" disabled={carregando}>
              {carregando ? "Guardando..." : "Guardar senha"}
            </button>
          </form>
        )}

        <button type="button" className="login-alternar" onClick={onConcluido}>
          Ir para a entrada
        </button>
      </div>
    </div>
  );
}
