import { useEffect, useState } from "react";

import { mensagemDeErro } from "./Registo";

import { API_URL } from "./api";

// Texto da confirmação antes de aprovar: avisa se o cliente perde oportunidades.
export function textoConfirmacaoAprovar(pedido) {
  const base = `Aprovar ${pedido.usuario?.nome || "este utilizador"} como corretor (CRECI ${pedido.creci})?`;
  const n = Number(pedido.oportunidades_como_cliente) || 0;
  if (!n) return base;
  return (
    `${base}\n\nAtenção: tem ${n} oportunidade${n === 1 ? "" : "s"} como cliente, ` +
    "que deixa de ver depois de virar corretor."
  );
}

function PedidosCorretorAdmin({ token, onDecidido }) {
  const [pedidos, setPedidos] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [decidindoId, setDecidindoId] = useState(null);

  async function carregar() {
    try {
      setCarregando(true);
      setErro("");
      const resposta = await fetch(`${API_URL}/admin/pedidos-corretor?status=PENDENTE`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        throw new Error(mensagemDeErro(dados, "Não foi possível carregar os pedidos."));
      }
      setPedidos(Array.isArray(dados) ? dados : []);
    } catch (error) {
      setErro(error.message);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function decidir(pedido, acao) {
    let corpo;
    if (acao === "aprovar") {
      if (!window.confirm(textoConfirmacaoAprovar(pedido))) return;
    } else {
      const motivo = window.prompt("Motivo da rejeição (opcional, o utilizador vê este texto):", "");
      if (motivo === null) return;
      corpo = JSON.stringify({ motivo });
    }

    try {
      setDecidindoId(pedido.id);
      setErro("");
      const resposta = await fetch(`${API_URL}/admin/pedidos-corretor/${pedido.id}/${acao}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: corpo,
      });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) {
        throw new Error(mensagemDeErro(dados, "Não foi possível decidir o pedido."));
      }
      setPedidos((lista) => lista.filter((item) => item.id !== pedido.id));
      onDecidido?.();
    } catch (error) {
      setErro(error.message);
    } finally {
      setDecidindoId(null);
    }
  }

  return (
    <section className="admin-section admin-pedidos-corretor">
      <div className="admin-section-heading">
        <div className="admin-section-title">
          <span>NOVOS CORRETORES</span>
          <h2>Pedidos de conta de corretor</h2>
        </div>
        <button type="button" className="admin-secondary-button" onClick={carregar}>
          Atualizar
        </button>
      </div>

      {erro && <p className="admin-error" role="alert">{erro}</p>}

      {carregando ? (
        <p>Carregando pedidos...</p>
      ) : pedidos.length === 0 ? (
        <p>Nenhum pedido pendente.</p>
      ) : (
        <div className="admin-pedidos-lista">
          {pedidos.map((pedido) => (
            <article key={pedido.id} className="admin-pedido-card">
              <div>
                <strong>{pedido.usuario?.nome}</strong> · {pedido.usuario?.email}
              </div>
              <div>
                CRECI <strong>{pedido.creci}</strong>
                {pedido.telefone && <> · {pedido.telefone}</>}
                {pedido.imobiliaria && <> · {pedido.imobiliaria}</>}
              </div>
              {pedido.oportunidades_como_cliente > 0 && (
                <div className="admin-pedido-aviso">
                  Tem {pedido.oportunidades_como_cliente} oportunidade(s) como cliente.
                </div>
              )}
              <div className="admin-pedido-acoes">
                <button
                  type="button"
                  className="admin-primary-button"
                  disabled={decidindoId === pedido.id}
                  onClick={() => decidir(pedido, "aprovar")}
                >
                  Aprovar
                </button>
                <button
                  type="button"
                  className="admin-secondary-button"
                  disabled={decidindoId === pedido.id}
                  onClick={() => decidir(pedido, "rejeitar")}
                >
                  Rejeitar
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default PedidosCorretorAdmin;
