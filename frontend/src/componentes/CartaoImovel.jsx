// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
import { Bath, BedDouble, Car, Columns3, ExternalLink, Heart, Home, Image as ImageIcon, Info, MapPin, Ruler, Tag } from "lucide-react";
import { alertasDoImovel, decisaoDaOportunidade, detalhesDoScore, dinheiro, prioridadeDoImovel } from "../imovel/analise";

export default function CartaoImovel({
  abrirDetalhes,
  abrirGaleria,
  alternarComparacao,
  alternarFavorito,
  favoritos,
  imoveisComparacao,
  imovel,
  papel,
}) {
  const fotos = Array.isArray(imovel.imagens)
    ? imovel.imagens
    : imovel.imagem
      ? [imovel.imagem]
      : [];

  const detalhesCard = detalhesDoScore(imovel);
  const oportunidade = detalhesCard;
  const economia = detalhesCard.economia;
  const analise = detalhesCard.analise;
  const descontoCalculado = detalhesCard.desconto;
  const decisao = decisaoDaOportunidade(imovel);
  const alertas = alertasDoImovel(imovel);
  const prioridade = prioridadeDoImovel(imovel);
  const IconeDecisao = decisao.Icone;
  const economiaPorM2 = detalhesCard.economiaPorM2;
  const condicoesCompra = detalhesCard.condicoesCompra;

  return (
    <article
      className="card"
      key={imovel.id}
    >

      {/* IMAGEM */}
      <div className="card-image">

        {/* FAVORITO */}
        {papel !== "corretor" && <button
          type="button"
          className={`favorite-button ${
            favoritos.some((id) => String(id) === String(imovel.id)) ? "favorited" : ""
          }`}
          onClick={(event) => {
            event.stopPropagation();
            alternarFavorito(imovel);
          }}
          aria-label={
            favoritos.some((id) => String(id) === String(imovel.id))
              ? "Remover dos favoritos"
              : "Adicionar aos favoritos"
          }
        >
          <Heart
            size={20}
            fill={favoritos.some((id) => String(id) === String(imovel.id)) ? "currentColor" : "none"}
          />
        </button>}

        {/* BADGE */}
        <div className="auction-badge">
          {"\u{1F528}"} LEILÃO SFI
        </div>

        {/* FOTO */}
        {fotos.length > 0 ? (

          <button
            type="button"
            className="image-button"
            onClick={() =>
              abrirGaleria(
                imovel
              )
            }
            aria-label={`Abrir fotos de ${imovel.titulo}`}
          >

            <img
              src={fotos[0]}
              alt={
                imovel.titulo ||
                "Imóvel"
              }
              loading="lazy"
              decoding="async"
              onError={(event) => {

                event.currentTarget.style.display =
                  "none";

                const placeholder =
                  event
                    .currentTarget
                    .parentElement
                    ?.parentElement
                    ?.querySelector(
                      ".image-placeholder"
                    );

                if (
                  placeholder
                ) {
                  placeholder.style.display =
                    "flex";
                }

              }}
            />

            <span className="image-overlay">

              <ImageIcon
                size={17}
              />

              Ver foto

            </span>

          </button>

        ) : null}

        {/* PLACEHOLDER */}
        <div
          className="image-placeholder"
          style={{
            display:
              fotos.length > 0
                ? "none"
                : "flex",
          }}
        >

          <Home size={44} />

          <span>
            Imóvel de leilão
          </span>

        </div>

      </div>

      {/* CONTEÚDO */}
      <div className="card-body">

        <button type="button" className={`compare-select ${imoveisComparacao.some((item) => String(item.id) === String(imovel.id)) ? "selected" : ""}`} onClick={() => alternarComparacao(imovel)} aria-pressed={imoveisComparacao.some((item) => String(item.id) === String(imovel.id))}>
          <Columns3 size={15} /> {imoveisComparacao.some((item) => String(item.id) === String(imovel.id)) ? "Selecionado para comparar" : "Comparar oportunidade"}
        </button>

        {/* ALERTAS */}
        {alertas.length > 0 && (
          <div className="card-alerts">
            {alertas.map((alerta, index) => (
              <span
                key={`${imovel.id}-alerta-${index}`}
                className={`card-alert ${alerta.tipo}`}
              >
                {alerta.tipo === "danger"
                  ? "🔴"
                  : alerta.tipo === "warning"
                    ? "⚠️"
                    : "ℹ️"}{" "}
                {alerta.texto}
              </span>
            ))}
          </div>
        )}

        {/* TÍTULO */}
        <h3 className="card-title">
          {imovel.titulo ||
            "Imóvel"}
        </h3>

        {/* LOCALIZAÇÃO */}
        <div className="location">

          <MapPin size={16} />

          <span>
            {imovel.cidade ||
              "Cidade não informada"}

            {imovel.estado
              ? ` - ${imovel.estado}`
              : ""}
          </span>

        </div>

        {/* TIPO */}
        <div className="property-type">

          <Tag size={15} />

          {imovel.tipo ||
            "Tipo não informado"}

        </div>

        {/* CARACTERÍSTICAS */}
        {(imovel.area_util ||
          imovel.quartos ||
          imovel.banheiros ||
          imovel.vagas) && (
          <div className="property-features">

            {imovel.area_util && (
              <span>
                <Ruler size={16} />
                {imovel.area_util} m²
              </span>
            )}

            {imovel.quartos && (
              <span>
                <BedDouble size={16} />
                {imovel.quartos} quartos
              </span>
            )}

            {imovel.banheiros && (
              <span>
                <Bath size={16} />
                {imovel.banheiros} banheiros
              </span>
            )}

            {imovel.vagas && (
              <span>
                <Car size={16} />
                {imovel.vagas} vagas
              </span>
            )}

          </div>
        )}

        {/* DESCONTO */}
        {descontoCalculado !== null &&
          descontoCalculado > 0 && (
            <div className="discount-info">
              💰 DESCONTO{" "}
              <strong>
                {descontoCalculado
                  .toFixed(2)
                  .replace(".",",")}
                % OFF
              </strong>
            </div>
          )}

        {/* PRIORIDADE */}
      <div className={`prioridade-badge ${prioridade.classe}`}>
        {prioridade.nivel === "p1" && "🔥"}
        {prioridade.nivel === "p2" && "⚡"}
        {prioridade.nivel === "p3" && "🔎"}
        {prioridade.nivel === "p4" && "👁️"}
        {prioridade.nivel === "fora" && "?"}
        {" "}
        {prioridade.label}
      </div>

        {/* SCORE DA OPORTUNIDADE */}
        <div className={`opportunity-score ${oportunidade.classe}`}>
          <div className="opportunity-score-header">
            <span>Score da oportunidade</span>
            <strong>{oportunidade.valor}/100</strong>
          </div>
          <div
            className="opportunity-score-track"
            role="progressbar"
            aria-label={`Score da oportunidade: ${oportunidade.valor} de 100`}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow={oportunidade.valor}
          >
            <span
              className="opportunity-score-fill"
              style={{ width: `${oportunidade.valor}%` }}
            />
          </div>
          <span className="opportunity-score-label">
            {oportunidade.texto}
          </span>
          <details className="score-explanation">
            <summary>
              <Info size={14} aria-hidden="true" />
              Ver composição do score
            </summary>

            <div className="score-factors">
              <div className="score-factor">
                <span>Desconto</span>
                <strong>
                  {oportunidade.desconto === null
                    ? "Não informado"
                    : `${oportunidade.desconto.toFixed(2).replace(".", ",")}%`}
                </strong>
                <small>{oportunidade.pontosDesconto}/30 pontos</small>
              </div>
              <div className="score-factor">
                <span>Economia total</span>
                <strong>{economia > 0 ? dinheiro(economia) : "Não informado"}</strong>
                <small>{oportunidade.pontosEconomia}/15 pontos</small>
              </div>
              <div className="score-factor">
                <span>Economia por m²</span>
                <strong>
                  {economiaPorM2 !== null
                    ? `${dinheiro(economiaPorM2)}/m²`
                    : "Não informado"}
                </strong>
                <small>{oportunidade.pontosEconomiaM2}/10 pontos</small>
              </div>
              <div className="score-factor">
                <span>Dados essenciais</span>
                <strong>{oportunidade.dadosCompletos.filter(Boolean).length}/4 itens</strong>
                <small>{oportunidade.pontosDados}/15 pontos</small>
              </div>
              <div className="score-factor">
                <span>Data do leilão</span>
                <strong>
                  {oportunidade.leilaoJaRealizado
                    ? "Leilões já realizados"
                    : oportunidade.diasAteLeilao !== null
                      ? `${oportunidade.diasAteLeilao} dias`
                      : "Não informado"}
                </strong>
                <small>{oportunidade.pontosData}/10 pontos</small>
              </div>
            </div>

            {condicoesCompra.length > 0 && (
              <div className="score-conditions">
                {condicoesCompra.map((condicao) => (
                  <span key={condicao.nome}>
                    <strong>{condicao.nome}:</strong> {condicao.valor}
                  </span>
                ))}
              </div>
            )}
          </details>
        </div>

        <div
          className={`decision-indicator ${decisao.classe}`}
          aria-label={`Decisão da oportunidade: ${decisao.titulo}`}
        >
          <IconeDecisao size={18} aria-hidden="true" />
          <div>
            <span>Decisão da oportunidade</span>
            <strong>{decisao.titulo}</strong>
            <small>{decisao.descricao}</small>
          </div>
        </div>

        {/* ECONOMIA */}
        {economia > 0 && (

          <div className="economy">

            Você economiza{" "}

            <strong>
              {dinheiro(
                economia
              )}
            </strong>

          </div>

        )}

        {/* ANALISE FINANCEIRA*/}
        {(analise.valorM2Avaliacao || analise.valorM2Leilao) && (
          <div className="financial-analysis">

            <div className="financial-row">
              <span>Valor/m² avaliação</span>
              <strong>
                {analise.valorM2Avaliacao
                  ? dinheiro(analise.valorM2Avaliacao)
                  : "Não informado"}
              </strong>
            </div>

            <div className="financial-row">
              <span>Valor/m² leilão</span>
              <strong>
                {analise.valorM2Leilao
                  ? dinheiro(analise.valorM2Leilao)
                  : "Não informado"}
              </strong>
            </div>
            {analise.valorM2Avaliacao && analise.valorM2Leilao && (
              <div className="financial-saving">
                Economia por m²{" "}
                <strong>
                  {imovel.economia_m2 !== null && imovel.economia_m2 !== undefined
                    ? `${dinheiro(imovel.economia_m2)}/m²`
                    : "Não informado"}
                </strong>
              </div>
            )}

          </div>
        )}

        {/* ENDEREÇO */}
        {imovel.endereco && (

          <div className="address">

            <MapPin size={14} />

            <span>
              {imovel.endereco}
            </span>

          </div>

        )}

        {/* BOTÃO */}
        <button
          type="button"
          className="view-button"
          onClick={() => abrirDetalhes(imovel)}
        >
          Ver oportunidade
          <ExternalLink size={17} />
        </button>

      </div>

    </article>

  );
}
