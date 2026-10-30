// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
export default function Paginacao({
  mudarPagina,
  pagina,
  paginas,
  paginasVisiveis,
}) {
  return (
    <div className="pagination">

      <button
        type="button"
        className="pagination-arrow"
        onClick={() =>
          mudarPagina(
            pagina - 1
          )
        }
        disabled={
          pagina === 1
        }
      >
        ←
      </button>

      {paginasVisiveis().map(
        (numero, index) =>
          numero === "..." ? (

            <span
              key={`ellipsis-${index}`}
              className="pagination-ellipsis"
            >
              ...
            </span>

          ) : (

            <button
              key={numero}
              type="button"
              className={`pagination-button ${pagina === numero
                  ? "active"
                  : ""
                }`}
              onClick={() =>
                mudarPagina(
                  numero
                )
              }
            >
              {numero}
            </button>

          )
      )}

      <button
        type="button"
        className="pagination-arrow"
        onClick={() =>
          mudarPagina(
            pagina + 1
          )
        }
        disabled={
          pagina === paginas
        }
      >
        →
      </button>

    </div>
  );
}
