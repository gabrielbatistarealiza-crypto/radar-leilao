// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
import { Gavel, LogOut } from "lucide-react";
import { Link } from "react-router-dom";
import { ROTULOS_PAPEL } from "../papel";

export default function Cabecalho({
  ehAdministrador,
  papel,
  sair,
}) {
  return (
    <header className="header">
      <div className="container header-content">

        <div className="logo">
          <div className="logo-icon">
            <Gavel size={24} />
          </div>

          <div>
            <h1>Radar Leilão</h1>
            <span>
              Encontre oportunidades
            </span>
          </div>
        </div>

        <div className="header-account">
          <span className="user-role-badge">
            {ROTULOS_PAPEL[papel] || "Papel não configurado"}
          </span>
          {papel === "cliente" && (
            <nav className="cliente-navigation" aria-label="Navegação do cliente">
              <a href="#meu-perfil">Meu perfil</a>
              <a href="#minhas-oportunidades">Minhas oportunidades</a>
              <a href="#alertas">Alertas</a>
              <a href="#consultoria">Dúvidas sobre leilão</a>
            </nav>
          )}
          {papel === "corretor" && (
            <nav className="cliente-navigation" aria-label="Navegação do corretor">
              <a href="#painel-corretor">Minhas oportunidades</a>
              <a href="#perfil-corretor">Meu perfil</a>
              <a href="#alertas">Alertas</a>
              <a href="#consultoria">Dúvidas sobre leilão</a>
            </nav>
          )}
          {papel === "admin" && (
            <nav className="cliente-navigation" aria-label="Navegação do administrador">
              <a href="#alertas">Alertas</a>
            </nav>
          )}
          {ehAdministrador && (
            <Link className="header-admin-link" to="/admin">
              Administração
            </Link>
          )}
          <button type="button" className="header-logout" onClick={sair}>
            <LogOut size={16} />
            Sair
          </button>
          <span className="header-status">
            <span className="status-dot" />
            Sistema online
          </span>
        </div>

      </div>
    </header>
  );
}
