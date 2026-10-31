// Página aberta pela ligação "deixar de receber" do resumo de alertas por e-mail.
// Funciona sem sessão: o token da ligação identifica a conta.
import { useEffect, useState } from "react";

import { pedirApi } from "./api";

export default function DesligarAlertas({ token, onConcluido }) {
  const [estado, setEstado] = useState(token ? "a-desligar" : "erro");
  const [mensagem, setMensagem] = useState(token ? "" : "Ligação incompleta.");

  useEffect(() => {
    if (!token) return undefined;
    let ativo = true;
    pedirApi("/alertas/email/desligar", { metodo: "POST", corpo: { token }, erroPadrao: "Ligação inválida." })
      .then((dados) => {
        if (!ativo) return;
        setEstado("feito");
        setMensagem(dados.mensagem);
      })
      .catch((falha) => {
        if (!ativo) return;
        setEstado("erro");
        setMensagem(falha instanceof TypeError ? "Não foi possível conectar à API. Tente daqui a pouco." : falha.message);
      });
    return () => {
      ativo = false;
    };
  }, [token]);

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Radar Leilão</h1>
        <p>Resumo dos alertas por e-mail</p>
        {estado === "a-desligar" && <p>A desligar…</p>}
        {estado === "feito" && <div className="login-ok" role="status">{mensagem}</div>}
        {estado === "erro" && <div className="login-error" role="alert">{mensagem}</div>}
        <button type="button" className="login-alternar" onClick={onConcluido}>
          Ir para o site
        </button>
      </div>
    </div>
  );
}
