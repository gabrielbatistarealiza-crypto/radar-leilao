// Interruptor do resumo diário dos alertas por e-mail (página de Alertas).
import { useEffect, useState } from "react";
import { Mail } from "lucide-react";

import { pedirApi } from "../api";

export default function ResumoPorEmail({ token }) {
  const [estado, setEstado] = useState(null); // {ativo, envio_configurado}
  const [guardando, setGuardando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    pedirApi("/alertas/email", { token })
      .then((dados) => ativo && setEstado(dados))
      .catch(() => ativo && setEstado(null)); // sem resposta: o interruptor não aparece
    return () => {
      ativo = false;
    };
  }, [token]);

  if (!estado) return null;

  const mudar = async (event) => {
    const novo = event.target.checked;
    setGuardando(true);
    setErro("");
    try {
      setEstado(await pedirApi("/alertas/email", { metodo: "PUT", corpo: { ativo: novo }, token }));
    } catch (falha) {
      setErro(falha.message || "Não foi possível guardar.");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="resumo-email">
      <label>
        <input type="checkbox" checked={estado.ativo} onChange={mudar} disabled={guardando} />
        <Mail size={16} aria-hidden="true" />
        Receber um resumo diário por e-mail com as novidades dos meus alertas
      </label>
      {!estado.envio_configurado && (
        <small>O envio de e-mails ainda não está ligado no servidor.</small>
      )}
      {erro && <small className="resumo-email-erro" role="alert">{erro}</small>}
    </div>
  );
}
