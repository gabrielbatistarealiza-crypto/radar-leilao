// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
import PedidoCorretor from "../PedidoCorretor";
import { ROTULOS_PAPEL } from "../papel";
import ApagarConta from "./ApagarConta";

export default function PerfilCliente({
  token,
  usuario,
  onContaApagada,
}) {
  return (
    <section id="meu-perfil" className="container cliente-profile-section">
      <div className="cliente-profile-card">
        <div className="cliente-profile-heading">
          <span className="section-kicker">MINHA CONTA</span>
          <h2>Meu perfil</h2>
        </div>
        <dl className="cliente-profile-details">
          <div>
            <dt>Nome</dt>
            <dd>{usuario.nome || "Não informado"}</dd>
          </div>
          <div>
            <dt>E-mail</dt>
            <dd>{usuario.email || "Não informado"}</dd>
          </div>
          <div>
            <dt>Tipo</dt>
            <dd>{ROTULOS_PAPEL[usuario.tipo] || usuario.tipo || "Não informado"}</dd>
          </div>
        </dl>
        <PedidoCorretor token={token} />
        <ApagarConta token={token} onApagada={onContaApagada} />
      </div>
    </section>
  );
}
