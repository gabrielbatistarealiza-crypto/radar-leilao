// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
import ApagarConta from "./ApagarConta";

export default function PerfilCorretor({
  usuario,
  token,
  onContaApagada,
}) {
  return (
    <section id="perfil-corretor" className="container cliente-profile-section">
      <div className="cliente-profile-card">
        <div className="cliente-profile-heading">
          <span className="section-kicker">MINHA CONTA</span>
          <h2>Meu perfil</h2>
        </div>
        <dl className="cliente-profile-details">
          <div><dt>Nome</dt><dd>{usuario.nome || "Não informado"}</dd></div>
          <div><dt>E-mail</dt><dd>{usuario.email || "Não informado"}</dd></div>
          <div><dt>Tipo</dt><dd>Corretor</dd></div>
        </dl>
        <ApagarConta token={token} onApagada={onContaApagada} />
      </div>
    </section>
  );
}
