// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
import { ExternalLink, Heart, Home, Image as ImageIcon, MapPin, X } from "lucide-react";
import Oportunidade from "../Oportunidade";
import { avisoForaDaLista } from "../foraDaLista";
import { calcularDesconto, calcularEconomia, dinheiro, formatarData, fotosDoImovel, valorInputFinanceiro, valoresDosLeiloes } from "../imovel/analise";

export default function DetalhesImovel({
  IconeDecisao,
  abrirGaleria,
  alternarFavorito,
  analiseDetalhes,
  atualizarCenarioSelecionado,
  atualizarCustoArremate,
  cenarioDetalhes,
  custosArremate,
  decisaoDetalhes,
  favoritos,
  fotoDetalhesAtiva,
  imovelDetalhes,
  oportunidadeDetalhes,
  oportunidadeSelecionada,
  papel,
  scoreDetalhes,
  setFotoDetalhesAtiva,
  setImovelDetalhes,
  token,
  usuario,
}) {
  return (
    <div
      className="details-modal"
      role="dialog"
      aria-modal="true"
      onClick={() => setImovelDetalhes(null)}
    >
      <div
        className="details-content"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          className="details-close"
          onClick={() => setImovelDetalhes(null)}
          aria-label="Fechar detalhes"
        >
          <X size={22} />
        </button>

        <div className="details-image">
          {fotosDoImovel(imovelDetalhes).length > 0 ? (
            <button
              type="button"
              className="details-image-button"
              onClick={() => abrirGaleria(imovelDetalhes)}
              aria-label={`Ver fotos de ${imovelDetalhes.titulo || "imóvel"}`}
            >
              <img
                src={
                  fotosDoImovel(imovelDetalhes)[fotoDetalhesAtiva] ||
                  fotosDoImovel(imovelDetalhes)[0]
                }
                alt={imovelDetalhes.titulo || "Imóvel"}
                onError={() => {
                  const fotosDetalhes = fotosDoImovel(imovelDetalhes);
                  setFotoDetalhesAtiva((atual) => {
                    if (atual >= fotosDetalhes.length - 1) return atual;
                    return atual + 1;
                  });
                }}
              />
              <span>
                <ImageIcon size={17} />
                Ver {fotosDoImovel(imovelDetalhes).length} foto(s)
              </span>
            </button>
          ) : (
            <div className="details-image-placeholder">
              <Home size={50} />
              <span>Imóvel de leilão</span>
            </div>
          )}
        </div>

        <div className="details-body">
          <span className="auction-badge">LEILÃO SFI</span>

          <h2>{imovelDetalhes.titulo || "Imóvel"}</h2>

          {avisoForaDaLista(imovelDetalhes) && (
            <div className="aviso-fora-da-lista" role="status">
              {avisoForaDaLista(imovelDetalhes)}
            </div>
          )}

          <div className="details-location">
            <MapPin size={17} />
            <span>
              {imovelDetalhes.cidade || "Cidade não informada"}
              {imovelDetalhes.estado ? ` - ${imovelDetalhes.estado}` : ""}
            </span>
          </div>

          {papel !== "corretor" && <button
            type="button"
            className={`details-favorite ${
              favoritos.some((id) => String(id) === String(imovelDetalhes.id))
                ? "favorited"
                : ""
            }`}
            onClick={() => alternarFavorito(imovelDetalhes)}
          >
            <Heart
              size={17}
              fill={
                favoritos.some((id) => String(id) === String(imovelDetalhes.id))
                  ? "currentColor"
                  : "none"
              }
            />
            {favoritos.some((id) => String(id) === String(imovelDetalhes.id))
              ? "Remover dos favoritos"
              : "Adicionar aos favoritos"}
          </button>}

          <div className="details-discount">
            💰 DESCONTO <strong>
              {(calcularDesconto(imovelDetalhes) || 0).toFixed(2).replace(".", ",")}% OFF
            </strong>
          </div>

          <div className="details-prices">
            <div>
              <span>Valor de avaliação</span>
              <strong>{dinheiro(imovelDetalhes.valor_avaliacao)}</strong>
            </div>
            {valoresDosLeiloes(imovelDetalhes) ? (
              <>
                <div>
                  <span>1.º leilão</span>
                  <strong>{dinheiro(valoresDosLeiloes(imovelDetalhes).primeiro)}</strong>
                </div>
                <div>
                  <span>2.º leilão</span>
                  <strong>{dinheiro(valoresDosLeiloes(imovelDetalhes).segundo)}</strong>
                </div>
                <div>
                  <span>Lance mínimo</span>
                  <strong>{dinheiro(imovelDetalhes.valor_leilao)}</strong>
                </div>
              </>
            ) : (
              <div>
                <span>Valor do leilão</span>
                <strong>{dinheiro(imovelDetalhes.valor_leilao)}</strong>
              </div>
            )}
            <div>
              <span>Você economiza</span>
              <strong>{dinheiro(calcularEconomia(imovelDetalhes))}</strong>
            </div>
          </div>

          <section
            className={`details-score opportunity-score ${oportunidadeDetalhes.classe}`}
            aria-label="Score da oportunidade"
          >
            <div className="opportunity-score-header">
              <span>Score da oportunidade</span>
              <strong>{oportunidadeDetalhes.valor}/100</strong>
            </div>
            <div
              className="opportunity-score-track"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={oportunidadeDetalhes.valor}
            >
              <span
                className="opportunity-score-fill"
                style={{ width: `${oportunidadeDetalhes.valor}%` }}
              />
            </div>
            <span className="opportunity-score-label">
              {oportunidadeDetalhes.texto}
            </span>
            <div className="score-factors details-score-factors">
              <div className="score-factor">
                <span>Desconto</span>
                <strong>
                  {scoreDetalhes.desconto === null
                    ? "Não informado"
                    : `${scoreDetalhes.desconto.toFixed(2).replace(".", ",")}%`}
                </strong>
                <small>{scoreDetalhes.pontosDesconto}/30 pontos</small>
              </div>

              <div className="score-factor">
                <span>Economia total</span>
                <strong>
                  {scoreDetalhes.economia > 0
                    ? dinheiro(scoreDetalhes.economia)
                    : "Não informado"}
                </strong>
                <small>{scoreDetalhes.pontosEconomia}/15 pontos</small>
              </div>

              <div className="score-factor">
                <span>Economia por m²</span>
                <strong>
                  {scoreDetalhes.economiaPorM2 !== null
                    ? `${dinheiro(scoreDetalhes.economiaPorM2)}/m²`
                    : "Não informado"}
                </strong>
                <small>{scoreDetalhes.pontosEconomiaM2}/10 pontos</small>
              </div>

              <div className="score-factor">
                <span>Dados essenciais</span>
                <strong>
                  {scoreDetalhes.dadosCompletos.filter(Boolean).length}/4 itens
                </strong>
                <small>{scoreDetalhes.pontosDados}/15 pontos</small>
              </div>

              <div className="score-factor">
                <span>Data do leilão</span>
                <strong>
                  {scoreDetalhes.leilaoJaRealizado
                    ? "Leilão já realizado"
                    : scoreDetalhes.diasAteLeilao !== null
                      ? `${scoreDetalhes.diasAteLeilao} dias`
                      : "Não informado"}
                </strong>
                <small>{scoreDetalhes.pontosData}/10 pontos</small>
              </div>

              <div className="score-factor">
                <span>Resultado financeiro</span>

                <strong>
                  {Number.isFinite(scoreDetalhes.roi)
                    ? `ROI ${scoreDetalhes.roi.toFixed(2).replace(".", ",")}%`
                    : "Não informado"}
                </strong>

                <small>
                  {scoreDetalhes.pontosFinanceiros}/20 pontos
                </small>
              </div>
            </div>
          </section>

          <Oportunidade
            imovel={imovelDetalhes}
            usuario={usuario}
            token={token}
            dinheiro={dinheiro}
            oportunidadeInicial={
              papel === "corretor"
                ? oportunidadeSelecionada
                : null
            }
            onCenarioSelecionado={atualizarCenarioSelecionado}
            cenarioSelecionadoId={cenarioDetalhes?.id ?? null}
          />

          <section
            className={`decision-indicator details-decision ${decisaoDetalhes.classe}`}
            aria-label={`Decisão da oportunidade: ${decisaoDetalhes.titulo}`}
          >
            <IconeDecisao size={22} aria-hidden="true" />
            <div>
              <span>Decisão da oportunidade</span>
              <strong>{decisaoDetalhes.titulo}</strong>
              <small>{decisaoDetalhes.descricao}</small>
            </div>
          </section>

          {/* ANÁLISE FINANCEIRA */}
          {analiseDetalhes && (
            <div className="financial-analysis">

              <h3>Análise financeira</h3>

              <div className="financial-grid">

                <div className="financial-card">
                  <span>Valor/m² avaliação</span>
                  <strong>
                    {dinheiro(analiseDetalhes.valorM2Avaliacao)}
                  </strong>
                </div>

                <div className="financial-card">
                  <span>Valor/m² leilão</span>
                  <strong>
                    {dinheiro(analiseDetalhes.valorM2Leilao)}
                  </strong>
                </div>

                <div className="financial-card">
                  <span>Economia por m²</span>
                  <strong>
                    {dinheiro(
                      analiseDetalhes.valorM2Avaliacao -
                      analiseDetalhes.valorM2Leilao
                    )}
                  </strong>
                </div>

              </div>

              <div className="financial-simulation">

                <h4>Simulação do investimento</h4>

                {cenarioDetalhes ? (
                  <>
                    <p>Valores do cenário selecionado: {cenarioDetalhes.nome}. A soma de custos considera os valores informados no cenário.</p>
                    <div className="financial-results">
                      <div><span>Preço de aquisição</span><strong>{dinheiro(cenarioDetalhes.preco_aquisicao)}</strong></div>
                      <div><span>Impostos e taxas</span><strong>{cenarioDetalhes.impostos_taxas == null ? "Não informado" : dinheiro(cenarioDetalhes.impostos_taxas)}</strong></div>
                      <div><span>Custos jurídicos</span><strong>{cenarioDetalhes.custos_juridicos == null ? "Não informado" : dinheiro(cenarioDetalhes.custos_juridicos)}</strong></div>
                      <div><span>Reformas</span><strong>{cenarioDetalhes.reformas == null ? "Não informado" : dinheiro(cenarioDetalhes.reformas)}</strong></div>
                      <div><span>Outras despesas</span><strong>{cenarioDetalhes.outras_despesas == null ? "Não informado" : dinheiro(cenarioDetalhes.outras_despesas)}</strong></div>
                      <div><span>Custo total</span><strong>{dinheiro(cenarioDetalhes.custo_total)}</strong></div>
                      <div><span>Revenda estimada</span><strong>{dinheiro(cenarioDetalhes.valor_revenda)}</strong></div>
                      <div><span>Lucro estimado</span><strong>{dinheiro(cenarioDetalhes.lucro_estimado)}</strong></div>
                      <div><span>ROI</span><strong>{cenarioDetalhes.roi == null ? "—" : `${Number(cenarioDetalhes.roi).toFixed(2).replace(".", ",")}%`}</strong></div>
                      <div><span>Margem sobre revenda</span><strong>{cenarioDetalhes.margem_revenda == null ? "—" : `${Number(cenarioDetalhes.margem_revenda).toFixed(2).replace(".", ",")}%`}</strong></div>
                    </div>
                    {cenarioDetalhes.custos_nao_informados?.length > 0 && <p className="simulador-alerta">Custos por confirmar: {cenarioDetalhes.custos_nao_informados.join(", ")}. ROI e margem não pontuam no score enquanto estes dados estiverem ausentes.</p>}
                  </>
                ) : (
                  <>

                <div className="financial-input-grid">

                  <label>
                    Comissão do leiloeiro
                    <input
                      type="number"
                      min="0"
                      value={valorInputFinanceiro(
                        custosArremate[imovelDetalhes.id]?.comissao ??
                          analiseDetalhes.comissao
                      )}
                      onChange={(e) =>
                        atualizarCustoArremate("comissao", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    ITBI
                    <input
                      type="number"
                      min="0"
                      value={valorInputFinanceiro(
                        custosArremate[imovelDetalhes.id]?.itbi ??
                        analiseDetalhes.itbi
                      )}
                      onChange={(e) =>
                        atualizarCustoArremate("itbi", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    Registro
                    <input
                      type="number"
                      min="0"
                      value={valorInputFinanceiro(
                        custosArremate[imovelDetalhes.id]?.registro ??
                        analiseDetalhes.registro
                      )}
                      onChange={(e) =>
                        atualizarCustoArremate("registro", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    Outros custos
                    <input
                      type="number"
                      min="0"
                      value={valorInputFinanceiro(
                        custosArremate[imovelDetalhes.id]?.outrosCustos ??
                        analiseDetalhes.outrosCustos
                      )}
                      onChange={(e) =>
                        atualizarCustoArremate("outrosCustos", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    Custo de reforma
                    <input
                      type="number"
                      min="0"
                      value={valorInputFinanceiro(
                        custosArremate[imovelDetalhes.id]?.custoReforma ??
                        analiseDetalhes.custoReforma
                      )}
                      onChange={(e) =>
                        atualizarCustoArremate("custoReforma", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    Venda estimada
                    <input
                      type="number"
                      min="0"
                      value={valorInputFinanceiro(
                        custosArremate[imovelDetalhes.id]?.valorRevenda ??
                        analiseDetalhes.valorRevenda
                      )}
                      onChange={(e) =>
                        atualizarCustoArremate("valorRevenda", e.target.value)
                      }
                    />
                  </label>

                  <label>
                    Custo da venda
                    <input
                      type="number"
                      min="0"
                      value={valorInputFinanceiro(
                        custosArremate[imovelDetalhes.id]?.custoVenda ??
                        analiseDetalhes.custoVenda
                      )}
                      onChange={(e) =>
                        atualizarCustoArremate("custoVenda", e.target.value)
                      }
                    />
                  </label>

                </div>

                <div className="financial-results">

                  <div>
                    <span>Arremate + custos</span>
                    <strong>
                      {dinheiro(analiseDetalhes.custoTotal)}
                    </strong>
                  </div>

                  <div>
                    <span>Custo de reforma</span>
                    <strong>
                      {dinheiro(analiseDetalhes.custoReforma)}
                    </strong>
                  </div>

                  <div>
                    <span>Investimento total</span>
                    <strong>
                      {dinheiro(analiseDetalhes.custoInvestimento)}
                    </strong>
                  </div>

                  <div>
                    <span>Venda estimada</span>
                    <strong>
                      {dinheiro(analiseDetalhes.valorRevenda)}
                    </strong>
                  </div>

                  <div>
                    <span>Lucro estimado</span>
                    <strong>
                      {dinheiro(analiseDetalhes.lucroRealEstimado)}
                    </strong>
                  </div>

                  <div>
                    <span>ROI estimado</span>
                    <strong>
                      {Number.isFinite(analiseDetalhes.retornoSobreInvestimento)
                        ? `${analiseDetalhes.retornoSobreInvestimento.toFixed(2).replace(".", ",")}%`
                        : "—"}
                    </strong>
                  </div>

                  <div>
                    <span>Margem de segurança</span>
                    <strong>
                      {Number.isFinite(analiseDetalhes.margemSeguranca)
                        ? `${analiseDetalhes.margemSeguranca.toFixed(2).replace(".", ",")}%`
                        : "—"}
                    </strong>
                  </div>

                </div>
                  </>
                )}

              </div>

            </div>
          )}


          <h3>Dados do leilão</h3>

          <div className="details-auction-grid">

            <div>
              <span>1º leilão</span>
              <strong>
                {imovelDetalhes.data_primeiro_leilao
                  ? formatarData(imovelDetalhes.data_primeiro_leilao)
                  : "Não informado"}
              </strong>
            </div>

            <div>
              <span>2º leilão</span>
              <strong>
                {imovelDetalhes.data_segundo_leilao
                  ? formatarData(imovelDetalhes.data_segundo_leilao)
                  : "Não informado"}
              </strong>
            </div>

            <div>
              <span>Licitação aberta</span>
              <strong>
                {imovelDetalhes.data_licitacao_aberta
                  ? formatarData(imovelDetalhes.data_licitacao_aberta)
                  : "Não informado"}
              </strong>
            </div>

            <div>
              <span>Modalidade</span>
              <strong>
                {imovelDetalhes.modalidade || "Não informado"}
              </strong>
            </div>

            <div>
              <span>Valor de avaliação</span>
              <strong>
                {Number.isFinite(Number(imovelDetalhes.valor_avaliacao))
                  ? Number(imovelDetalhes.valor_avaliacao).toLocaleString("pt-BR", {
                      style: "currency",
                      currency: "BRL",
                    })
                  : "Não informado"}
              </strong>
            </div>

            <div>
              <span>Valor do leilão</span>
              <strong>
                {Number.isFinite(Number(imovelDetalhes.valor_leilao))
                  ? Number(imovelDetalhes.valor_leilao).toLocaleString("pt-BR", {
                      style: "currency",
                      currency: "BRL",
                    })
                  : "Não informado"}
              </strong>
            </div>

            <div>
              <span>Área</span>
              <strong>
                {imovelDetalhes.area
                  ? `${Number(imovelDetalhes.area).toLocaleString("pt-BR")} m²`
                  : "Não informado"}
              </strong>
            </div>

            <div>
              <span>Quartos</span>
              <strong>
                {imovelDetalhes.quartos ?? "Não informado"}
              </strong>
            </div>

            <div>
              <span>Banheiros</span>
              <strong>
                {imovelDetalhes.banheiros ?? "Não informado"}
              </strong>
            </div>

            <div>
              <span>Vagas</span>
              <strong>
                {imovelDetalhes.vagas ?? "Não informado"}
              </strong>
            </div>

            <div className="details-auction-wide">
              <span>Leiloeiro</span>
              <strong>
                {imovelDetalhes.leiloeiro || "Não informado"}
              </strong>
            </div>

            <div className="details-auction-wide">
              <span>Processo</span>
              <strong>
                {imovelDetalhes.processo || "Não informado"}
              </strong>
            </div>

            <div className="details-auction-wide">
              <span>Endereço</span>
              <strong>
                {[
                  imovelDetalhes.endereco,
                  imovelDetalhes.cidade,
                  imovelDetalhes.estado,
                ]
                  .filter(Boolean)
                  .join(" - ") || "Não informado"}
              </strong>
            </div>

          </div>

          <div className="details-actions">
            {imovelDetalhes.link_edital && (
              <a
                href={imovelDetalhes.link_edital}
                target="_blank"
                rel="noopener noreferrer"
                className="details-button secondary"
              >
                🔗 Ver edital <ExternalLink size={17} />
              </a>
            )}
            {imovelDetalhes.url && (
              <a
                href={imovelDetalhes.url}
                target="_blank"
                rel="noopener noreferrer"
                className="details-button"
              >
                🔗 Ver anúncio original <ExternalLink size={17} />
              </a>
            )}
            <button
              type="button"
              className="details-button secondary"
              onClick={() => setImovelDetalhes(null)}
            >
              Voltar para a lista
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
