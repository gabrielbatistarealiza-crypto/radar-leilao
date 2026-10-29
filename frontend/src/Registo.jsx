import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export const SENHA_MINIMA = 8;

// Devolve a primeira mensagem de erro, ou "" se o formulário está pronto a enviar.
export function validarRegisto({ nome, email, senha, confirmacao, souCorretor, creci }) {
  if (!String(nome || "").trim()) return "Indique o seu nome.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || "").trim())) {
    return "Indique um e-mail válido.";
  }
  if (String(senha || "").length < SENHA_MINIMA) {
    return `A senha precisa de pelo menos ${SENHA_MINIMA} caracteres.`;
  }
  if (senha !== confirmacao) return "As senhas não coincidem.";
  if (souCorretor && !/\d/.test(String(creci || ""))) {
    return "Indique o seu CRECI (ex.: CRECI-SP 123456-F).";
  }
  return "";
}

// A API devolve detail como texto ou, na validação, como lista de erros.
export function mensagemDeErro(dados, padrao) {
  const detalhe = dados?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe) && detalhe.length) {
    const msg = String(detalhe[0]?.msg || "");
    return msg.replace(/^Value error,\s*/i, "") || padrao;
  }
  return padrao;
}

function Registo({ onRegistado, onVoltar }) {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [souCorretor, setSouCorretor] = useState(false);
  const [creci, setCreci] = useState("");
  const [telefone, setTelefone] = useState("");
  const [imobiliaria, setImobiliaria] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  const registar = async (e) => {
    e.preventDefault();
    const problema = validarRegisto({ nome, email, senha, confirmacao, souCorretor, creci });
    if (problema) {
      setErro(problema);
      return;
    }

    setErro("");
    setEnviando(true);
    try {
      const corpo = { nome: nome.trim(), email: email.trim(), senha };
      if (souCorretor) {
        corpo.corretor = {
          creci: creci.trim(),
          telefone: telefone.trim() || null,
          imobiliaria: imobiliaria.trim() || null,
        };
      }
      const resposta = await fetch(`${API_URL}/registo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo),
      });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        throw new Error(mensagemDeErro(dados, "Não foi possível criar a conta."));
      }
      localStorage.setItem("radar-leilao-token", dados.access_token);
      onRegistado(dados.access_token, dados);
    } catch (error) {
      setErro(
        error instanceof TypeError
          ? "Não foi possível conectar à API. Tente novamente."
          : error.message
      );
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Radar Leilão</h1>
        <p>Criar conta</p>

        <form onSubmit={registar} noValidate>
          <label>
            Nome
            <input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={150} required />
          </label>
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
              placeholder={`Pelo menos ${SENHA_MINIMA} caracteres`}
              maxLength={128}
              required
            />
          </label>
          <label>
            Confirmar senha
            <input
              type="password"
              value={confirmacao}
              onChange={(e) => setConfirmacao(e.target.value)}
              maxLength={128}
              required
            />
          </label>

          <label className="registo-opcao">
            <input
              type="checkbox"
              checked={souCorretor}
              onChange={(e) => setSouCorretor(e.target.checked)}
            />
            Sou corretor e quero anunciar e atender clientes
          </label>

          {souCorretor && (
            <>
              <label>
                CRECI
                <input
                  value={creci}
                  onChange={(e) => setCreci(e.target.value)}
                  placeholder="CRECI-SP 123456-F"
                  maxLength={60}
                />
              </label>
              <label>
                Telefone (opcional)
                <input value={telefone} onChange={(e) => setTelefone(e.target.value)} maxLength={30} />
              </label>
              <label>
                Imobiliária (opcional)
                <input value={imobiliaria} onChange={(e) => setImobiliaria(e.target.value)} maxLength={150} />
              </label>
              <p className="registo-aviso">
                A conta de corretor fica ativa depois de um administrador verificar o CRECI.
                Até lá, pode usar a conta como cliente.
              </p>
            </>
          )}

          {erro && <div className="login-error" role="alert">{erro}</div>}

          <button type="submit" disabled={enviando}>
            {enviando ? "Criando conta..." : "Criar conta"}
          </button>
        </form>

        <button type="button" className="login-alternar" onClick={onVoltar}>
          Já tenho conta. Entrar
        </button>
      </div>
    </div>
  );
}

export default Registo;
