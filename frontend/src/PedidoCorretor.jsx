import { useEffect, useState } from "react";

import { mensagemDeErro } from "./Registo";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// Cartão no perfil do cliente: estado do pedido de corretor ou formulário para pedir.
function PedidoCorretor({ token }) {
  const [pedido, setPedido] = useState(undefined); // undefined = a carregar
  const [aberto, setAberto] = useState(false);
  const [creci, setCreci] = useState("");
  const [telefone, setTelefone] = useState("");
  const [imobiliaria, setImobiliaria] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    let ativo = true;
    fetch(`${API_URL}/pedidos-corretor/meu`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : { pedido: null }))
      .then((dados) => ativo && setPedido(dados?.pedido ?? null))
      .catch(() => ativo && setPedido(null));
    return () => {
      ativo = false;
    };
  }, [token]);

  async function enviar(e) {
    e.preventDefault();
    if (!/\d/.test(creci)) {
      setErro("Indique o seu CRECI (ex.: CRECI-SP 123456-F).");
      return;
    }
    try {
      setEnviando(true);
      setErro("");
      const resposta = await fetch(`${API_URL}/pedidos-corretor`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          creci: creci.trim(),
          telefone: telefone.trim() || null,
          imobiliaria: imobiliaria.trim() || null,
        }),
      });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        throw new Error(mensagemDeErro(dados, "Não foi possível enviar o pedido."));
      }
      setPedido(dados);
      setAberto(false);
    } catch (error) {
      setErro(error.message);
    } finally {
      setEnviando(false);
    }
  }

  if (pedido === undefined) return null;

  if (pedido?.status === "PENDENTE") {
    return (
      <p className="pedido-corretor-estado">
        Pedido de conta de corretor enviado (CRECI {pedido.creci}). Aguarda a verificação de um
        administrador.
      </p>
    );
  }

  if (pedido?.status === "APROVADO") {
    return (
      <p className="pedido-corretor-estado">
        Pedido aprovado. Recarregue a página para usar a conta de corretor.
      </p>
    );
  }

  return (
    <div className="pedido-corretor">
      {pedido?.status === "REJEITADO" && (
        <p className="pedido-corretor-estado">
          O último pedido de corretor foi rejeitado{pedido.motivo ? `: ${pedido.motivo}` : "."}
        </p>
      )}

      {!aberto ? (
        <button type="button" className="admin-secondary-button" onClick={() => setAberto(true)}>
          Sou corretor: pedir conta de corretor
        </button>
      ) : (
        <form onSubmit={enviar} className="pedido-corretor-form">
          <label>
            CRECI
            <input value={creci} onChange={(e) => setCreci(e.target.value)} placeholder="CRECI-SP 123456-F" maxLength={60} />
          </label>
          <label>
            Telefone (opcional)
            <input value={telefone} onChange={(e) => setTelefone(e.target.value)} maxLength={30} />
          </label>
          <label>
            Imobiliária (opcional)
            <input value={imobiliaria} onChange={(e) => setImobiliaria(e.target.value)} maxLength={150} />
          </label>
          {erro && <div className="login-error" role="alert">{erro}</div>}
          <button type="submit" disabled={enviando}>
            {enviando ? "Enviando..." : "Enviar pedido"}
          </button>
          <button type="button" className="login-alternar" onClick={() => setAberto(false)}>
            Cancelar
          </button>
        </form>
      )}
    </div>
  );
}

export default PedidoCorretor;
