// "Apagar a minha conta" (LGPD): pede a senha e explica o que se perde antes de apagar.
import { useState } from "react";

import { pedirApi } from "../api";

export default function ApagarConta({ token, onApagada }) {
  const [aberto, setAberto] = useState(false);
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [apagando, setApagando] = useState(false);

  const confirmar = async (e) => {
    e.preventDefault();
    setErro("");
    setApagando(true);
    try {
      await pedirApi("/usuarios/me/apagar", {
        metodo: "POST",
        corpo: { senha },
        token,
        erroPadrao: "Não foi possível apagar a conta.",
      });
      onApagada?.();
    } catch (falha) {
      setErro(falha instanceof TypeError ? "Não foi possível conectar à API." : falha.message);
      setApagando(false);
    }
  };

  if (!aberto) {
    return (
      <div className="apagar-conta">
        <button type="button" className="apagar-conta-abrir" onClick={() => setAberto(true)}>
          Apagar a minha conta
        </button>
      </div>
    );
  }

  return (
    <form className="apagar-conta apagar-conta-aberto" onSubmit={confirmar}>
      <strong>Apagar a conta e os seus dados</strong>
      <p>
        Isto apaga definitivamente a sua conta, alertas, notificações e as oportunidades em que é
        cliente (com negociações e simulações). Se for corretor, apaga também o perfil e os anúncios;
        as oportunidades dos seus clientes ficam, sem corretor. Não dá para desfazer.
      </p>
      <label>
        Confirme com a sua senha
        <input
          type="password"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      {erro && <div className="login-error" role="alert">{erro}</div>}
      <div className="apagar-conta-botoes">
        <button type="submit" className="apagar-conta-confirmar" disabled={apagando}>
          {apagando ? "Apagando..." : "Apagar definitivamente"}
        </button>
        <button type="button" className="apagar-conta-cancelar" onClick={() => { setAberto(false); setSenha(""); setErro(""); }}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
