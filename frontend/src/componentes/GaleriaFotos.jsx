// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
import { fotosDoImovel } from "../imovel/analise";

export default function GaleriaFotos({
  fotoAnterior,
  fotoAtiva,
  galeriaAberta,
  proximaFoto,
  setFotoAtiva,
  setGaleriaAberta,
}) {
  const fotos = fotosDoImovel(galeriaAberta);

  return (
    <div
      className="gallery-modal"
      role="dialog"
      aria-modal="true"
      aria-label={`Fotos de ${galeriaAberta.titulo || "imóvel"}`}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          setGaleriaAberta(null);
        }
      }}
    >
      <div className="gallery-content">
        <button
          type="button"
          className="gallery-close"
          onClick={() => setGaleriaAberta(null)}
          aria-label="Fechar galeria"
        >
          ×
        </button>

        {fotos.length > 0 && (
          <>
            <div className="gallery-main">
              <img
                src={fotos[fotoAtiva] || fotos[0]}
                alt={`Foto ${fotoAtiva + 1} de ${fotos.length}`}
                onError={() => {
                  setFotoAtiva((atual) => {
                    if (fotos.length <= 1 || atual >= fotos.length - 1) return atual;
                    return atual + 1;
                  });
                }}
              />

              {fotos.length > 1 && (
                <>
                  <button
                    type="button"
                    className="gallery-nav gallery-prev"
                    onClick={fotoAnterior}
                    aria-label="Foto anterior"
                  >
                    ‹
                  </button>

                  <button
                    type="button"
                    className="gallery-nav gallery-next"
                    onClick={proximaFoto}
                    aria-label="Próxima foto"
                  >
                    ›
                  </button>
                </>
              )}
            </div>

            <div className="gallery-footer">
              <strong>{galeriaAberta.titulo || "Imóvel"}</strong>
              <span>{fotoAtiva + 1} de {fotos.length}</span>
            </div>

            {fotos.length > 1 && (
              <div
                className="gallery-thumbnails"
                onClick={(event) => event.stopPropagation()}
              >
                {fotos.map((fotoUrl, indice) => (
                  <button
                    type="button"
                    className={indice === fotoAtiva ? "active" : ""}
                    key={`${fotoUrl}-${indice}`}
                    onClick={() => setFotoAtiva(indice)}
                    aria-label={`Abrir foto ${indice + 1}`}
                  >
                    <img
                      src={fotoUrl}
                      alt={`Miniatura da foto ${indice + 1}`}
                      loading="lazy"
                    />
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
