// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
import { Gavel, Search } from "lucide-react";

export default function TopoPesquisa({
  busca,
  pesquisar,
  setBusca,
}) {
  return (
      <section className="hero">
      <div className="container">

        <div className="hero-text">

          <span className="hero-label">
            <Gavel size={16} />
            OPORTUNIDADES EM LEILÕES
          </span>

          <h2>
            Encontre imóveis abaixo
            <br />
            <strong>
              do valor de mercado.
            </strong>
          </h2>

          <p>
            Pesquise imóveis de leilão,
            compare valores e encontre as
            melhores oportunidades.
          </p>

        </div>

        {/* BUSCA */}
        <form
          className="search-box"
          onSubmit={pesquisar}
        >

          <div className="search-input">

            <Search size={22} />

            <input
              type="text"
              placeholder="Digite cidade ou região..."
              value={busca}
              onChange={(event) =>
                setBusca(event.target.value)
              }
            />

          </div>

          <button
            type="submit"
            className="search-button"
          >
            <Search size={18} />
            Pesquisar
          </button>

        </form>

      </div>
    </section>
  );
}
