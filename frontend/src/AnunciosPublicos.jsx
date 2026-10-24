import { useEffect, useState } from "react";
import {
  Home,
  MapPin,
  Image as ImageIcon,
  ExternalLink,
  LoaderCircle,
  X,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function dinheiro(valor) {
  const numero = Number(valor);

  if (!Number.isFinite(numero)) {
    return "Não informado";
  }

  return numero.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export default function AnunciosPublicos({ usuario, token }) {
  const [anuncios, setAnuncios] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [anuncioSelecionado, setAnuncioSelecionado] = useState(null);
  const [carregandoInteresse, setCarregandoInteresse] = useState(null);
  const [mensagem, setMensagem] = useState("");

  async function carregarAnuncios() {
    setCarregando(true);
    setErro("");

    try {
      const resposta = await fetch(
        `${API_URL}/anuncios-imoveis/publicados`
      );

      const dados = await resposta.json().catch(() => null);

      if (!resposta.ok) {
        throw new Error(
          dados?.detail ||
            "Não foi possível carregar os imóveis anunciados."
        );
      }

      setAnuncios(Array.isArray(dados) ? dados : []);
    } catch (error) {
      console.error("Erro ao carregar anúncios públicos:", error);
      setErro(
        error.message ||
          "Não foi possível carregar os imóveis anunciados."
      );
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregarAnuncios();
  }, []);

  if (carregando) {
    return (
      <section className="anuncios-publicos-section">
        <div className="anuncios-publicos-loading">
          <LoaderCircle size={24} className="spin" />
          <span>Carregando imóveis anunciados...</span>
        </div>
      </section>
    );
  }

  async function demonstrarInteresse(anuncio) {
  if (!token || !usuario?.id) {
    setErro("Faça login para demonstrar interesse.");
    return;
  }

  if (usuario.tipo !== "cliente") {
    setErro("Apenas clientes podem demonstrar interesse.");
    return;
  }

  try {
    setCarregandoInteresse(anuncio.id);
    setErro("");
    setMensagem("");

    const resposta = await fetch(`${API_URL}/oportunidades`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        imovel_id: null,
        anuncio_id: anuncio.id,
        cliente_id: usuario.id,
        corretor_id: null,
        valor_imovel:
          anuncio.valor_anunciado != null
            ? Number(anuncio.valor_anunciado)
            : null,
        observacoes: `Interesse no anúncio "${anuncio.titulo}".`,
      }),
    });

    const dados = await resposta.json().catch(() => null);

    if (!resposta.ok) {
      throw new Error(
        dados?.detail ||
          `Não foi possível registrar o interesse (${resposta.status}).`
      );
    }

    setMensagem(
      `Interesse registrado em "${anuncio.titulo}".`
    );
  } catch (error) {
    console.error("Erro ao demonstrar interesse:", error);

    setErro(
      error.message ||
        "Não foi possível registrar o interesse."
    );
  } finally {
    setCarregandoInteresse(null);
  }
}

  return (
    <section
      id="imoveis-anunciados"
      className="anuncios-publicos-section"
    >
      <div className="anuncios-publicos-header">
        <div>
          <span className="anuncios-publicos-kicker">
            IMÓVEIS ANUNCIADOS
          </span>

          <h2>Oportunidades de corretores</h2>

          <p>
            Imóveis selecionados por corretores parceiros do Radar Leilão.
          </p>
        </div>

        <button
          type="button"
          onClick={carregarAnuncios}
          disabled={carregando}
        >
          Atualizar
        </button>
      </div>

      {erro && (
        <div className="anuncios-publicos-error">
          {erro}
        </div>
      )}

      {!erro && anuncios.length === 0 && (
        <div className="anuncios-publicos-empty">
          <Home size={38} />
          <h3>Nenhum imóvel anunciado no momento</h3>
          <p>
            Novas oportunidades de corretores aparecerão aqui.
          </p>
        </div>
      )}

      {anuncios.length > 0 && (
        <div className="anuncios-publicos-grid">
          {anuncios.map((anuncio) => {
            const fotoPrincipal = anuncio.fotos?.[0]?.url || null;

            return (
              <article
                key={anuncio.id}
                className="anuncio-publico-card"
              >
                {/* FOTO */}
                <div
                  className="anuncio-publico-image"
                  onClick={() => setAnuncioSelecionado(anuncio)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      setAnuncioSelecionado(anuncio);
                    }
                  }}
                >
                  {fotoPrincipal ? (
                    <img
                      src={fotoPrincipal}
                      alt={anuncio.titulo}
                      loading="lazy"
                      onError={(event) => {
                        event.currentTarget.style.display = "none";
                        event.currentTarget.parentElement
                          ?.classList.add("sem-foto");
                      }}
                    />
                  ) : (
                    <div className="anuncio-publico-sem-foto">
                      <Home size={42} />
                      <span>Sem foto</span>
                    </div>
                  )}

                  <span className="anuncio-publico-discount">
                    {Number(anuncio.desconto || 0)
                      .toFixed(2)
                      .replace(".", ",")}
                    % OFF
                  </span>
                </div>

                {/* CONTEÚDO */}
                <div className="anuncio-publico-body">
                  <h3>{anuncio.titulo}</h3>

                  <div className="anuncio-publico-location">
                    <MapPin size={16} />
                    <span>
                      {anuncio.cidade || "Cidade não informada"}
                      {anuncio.estado
                        ? ` - ${anuncio.estado}`
                        : ""}
                    </span>
                  </div>

                  {/* PREÇOS */}
                  <div className="anuncio-publico-prices">
                    <div>
                      <span>Valor de mercado</span>
                      <strong>
                        {dinheiro(anuncio.valor_mercado)}
                      </strong>
                    </div>

                    <div>
                      <span>Valor anunciado</span>
                      <strong>
                        {dinheiro(anuncio.valor_anunciado)}
                      </strong>
                    </div>
                  </div>

                  {/* CARACTERÍSTICAS */}
                  <div className="anuncio-publico-meta">
                    {anuncio.tipo && (
                      <span>{anuncio.tipo}</span>
                    )}

                    {anuncio.area != null && (
                      <span>{anuncio.area} m²</span>
                    )}

                    {anuncio.quartos != null && (
                      <span>{anuncio.quartos} quartos</span>
                    )}

                    {anuncio.banheiros != null && (
                      <span>{anuncio.banheiros} banheiros</span>
                    )}

                    {anuncio.vagas != null && (
                      <span>{anuncio.vagas} vagas</span>
                    )}
                  </div>

                  {/* AÇÃO */}
                  <div className="anuncio-publico-actions">
                    <button
                      type="button"
                      className="anuncio-publico-interest-button"
                      onClick={() => demonstrarInteresse(anuncio)}
                      disabled={carregandoInteresse === anuncio.id}
                    >
                      {carregandoInteresse === anuncio.id
                        ? "Registrando..."
                        : "Tenho interesse"}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {anuncioSelecionado && (
        <div
          className="anuncio-publico-modal"
          onClick={() => setAnuncioSelecionado(null)}
        >
          <div
            className="anuncio-publico-modal-content"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="anuncio-publico-modal-close"
              onClick={() => setAnuncioSelecionado(null)}
            >
              <X size={20} />
            </button>

            
            <div className="anuncio-publico-modal-gallery">
              {anuncioSelecionado.fotos?.filter((foto) => foto.url).length > 0 ? (
                anuncioSelecionado.fotos
                  .filter((foto) => foto.url)
                  .map((foto, index) => (
                    <img
                      key={foto.id ?? `${foto.url}-${index}`}
                      src={foto.url}
                      alt={`${anuncioSelecionado.titulo} - Foto ${index + 1}`}
                      loading="lazy"
                    />
                  ))
              ) : (
                <div className="anuncio-publico-sem-foto">
                  Sem fotografias disponíveis
                </div>
              )}
            </div>


            <div className="anuncio-publico-modal-body">
              <span className="anuncios-publicos-kicker">
                IMÓVEL ANUNCIADO
              </span>

              {erro && (
                <div className="anuncio-publico-alert error">
                  {erro}
                </div>
              )}

              {mensagem && (
                <div className="anuncio-publico-alert success">
                  {mensagem}
                </div>
              )}

              <h2>{anuncioSelecionado.titulo}</h2>

              <p>
                <MapPin size={16} />
                {anuncioSelecionado.cidade ||
                  "Cidade não informada"}
                {anuncioSelecionado.estado
                  ? ` - ${anuncioSelecionado.estado}`
                  : ""}
              </p>

              <div className="anuncio-publico-modal-values">
                <div>
                  <span>Valor de mercado</span>
                  <strong>
                    {dinheiro(
                      anuncioSelecionado.valor_mercado
                    )}
                  </strong>
                </div>

                <div>
                  <span>Valor anunciado</span>
                  <strong>
                    {dinheiro(
                      anuncioSelecionado.valor_anunciado
                    )}
                  </strong>
                </div>

                <div>
                  <span>Desconto</span>
                  <strong>
                    {Number(
                      anuncioSelecionado.desconto || 0
                    ).toFixed(2)}
                    %
                  </strong>
                </div>
              </div>

              {anuncioSelecionado.descricao && (
                <div className="anuncio-publico-description">
                  <h3>Descrição</h3>
                  <p>{anuncioSelecionado.descricao}</p>
                </div>
              )}

              {usuario ? (
                <button
                  type="button"
                  className="anuncio-publico-interest-button"
                  onClick={() => demonstrarInteresse(anuncioSelecionado)}
                  disabled={
                    carregandoInteresse === anuncioSelecionado.id
                  }
                >
                  {carregandoInteresse === anuncioSelecionado.id
                    ? "Registrando..."
                    : "Tenho interesse"}
                </button>
              ) : (
                <p className="anuncio-publico-login-hint">
                  Faça login para demonstrar interesse neste imóvel.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
