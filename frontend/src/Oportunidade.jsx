import { useEffect, useState } from "react";
import SimuladorRentabilidade from "./SimuladorRentabilidade";
import {
  CircleCheck,
  CircleX,
  Handshake,
  LoaderCircle,
  Plus,
  RefreshCw,
  ArrowRight,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const STATUS_OPORTUNIDADE = {
  interesse: "Interesse",
  em_contato: "Em contato",
  negociando: "Negociando",
  concluida: "Concluída",
  cancelada: "Cancelada",
};

const STATUS_NEGOCIACAO = {
  aberta: "Aberta",
  contraproposta: "Contraproposta",
  aceita: "Aceita",
  recusada: "Recusada",
  cancelada: "Cancelada",
};

const STATUS_OPERACAO = {
  em_andamento: "Em andamento",
  concluida: "Concluída",
  cancelada: "Cancelada",
};

function dataFormatada(valor) {
  if (!valor) return "—";
  const data = new Date(valor);
  return Number.isNaN(data.getTime()) ? "—" : data.toLocaleDateString("pt-BR");
}

function Oportunidade({ imovel, usuario, token, dinheiro, oportunidadeInicial = null, onCenarioSelecionado, cenarioSelecionadoId = null }) {
  const papelUsuario =
    usuario?.admin === true || usuario?.tipo === "admin"
      ? "admin"
      : ["cliente", "corretor"].includes(usuario?.tipo)
        ? usuario.tipo
        : null;
  const ehCliente = papelUsuario === "cliente";
  const ehCorretor = papelUsuario === "corretor";
  const ehAdministrador = papelUsuario === "admin";
  const podeGerenciarOportunidade = ehCorretor || ehAdministrador;
  const podeGerenciarNegociacao = ehCorretor || ehAdministrador;
  const podeGerenciarOperacao = podeGerenciarOportunidade;

  const [oportunidade, setOportunidade] = useState(null);
  const [negociacoes, setNegociacoes] = useState([]);
  const [operacao, setOperacao] = useState(null);

  const [carregando, setCarregando] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  const [observacoes, setObservacoes] = useState("");
  const [valorProposto, setValorProposto] = useState("");
  const [observacaoNegociacao, setObservacaoNegociacao] = useState("");
  const [valorOperacao, setValorOperacao] = useState("");
  const [mostrarContraproposta, setMostrarContraproposta] = useState(false);
  const [valorContraproposta, setValorContraproposta] = useState("");
  const [observacoesContraproposta, setObservacoesContraproposta] = useState("");

  async function requisicao(url, options = {}) {
    const resposta = await fetch(`${API_URL}${url}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${token}`,
        ...(options.headers || {}),
      },
    });

    const texto = await resposta.text();
    let dados = null;

    try {
      dados = texto ? JSON.parse(texto) : null;
    } catch {
      dados = null;
    }

    if (!resposta.ok) {
      throw new Error(
        dados?.detail || `Erro na API (${resposta.status}).`
      );
    }

    return dados;
  }

  async function carregarFluxo() {
    if (!imovel?.id || !usuario?.id || !token) return;

    setCarregando(true);
    setErro("");

    try {
      const caminhoOportunidades = ehCorretor
        ? `/oportunidades/corretor/${usuario.id}`
        : `/oportunidades/cliente/${usuario.id}`;
      const oportunidades = await requisicao(caminhoOportunidades);
      const encontrada = Array.isArray(oportunidades)
        ? oportunidades.find(
            (item) => ehCorretor && oportunidadeInicial?.id
              ? String(item.id) === String(oportunidadeInicial.id)
              : String(item.imovel_id) === String(imovel.id)
          )
        : null;

      setOportunidade(encontrada || null);
      setObservacoes(encontrada?.observacoes || "");

      if (!encontrada) {
        setNegociacoes([]);
        setOperacao(null);
        return;
      }

      const negociacoesDados = await requisicao(
        `/negociacoes/oportunidade/${encontrada.id}`
      );
      setNegociacoes(Array.isArray(negociacoesDados) ? negociacoesDados : []);

      try {
        const operacaoDados = await requisicao(
          `/operacoes/oportunidade/${encontrada.id}`
        );
        setOperacao(operacaoDados);
      } catch (error) {
        // 404 aqui significa apenas que a operação ainda não foi criada.
        if (!String(error.message).includes("404")) {
          console.warn("Não foi possível carregar a operação:", error);
        }
        setOperacao(null);
      }
    } catch (error) {
      console.error("Erro ao carregar fluxo da oportunidade:", error);
      setErro(error.message || "Não foi possível carregar a oportunidade.");
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregarFluxo();
  }, [imovel?.id, usuario?.id, token, oportunidadeInicial?.id, ehCorretor]);

  async function criarOportunidade() {
    if (!imovel?.id || !usuario?.id || !token) return;

    setSalvando(true);
    setErro("");

    try {
      const dados = await requisicao("/oportunidades", {
        method: "POST",
        body: JSON.stringify({
          imovel_id: imovel.id,
          cliente_id: usuario.id,
          corretor_id: null,
          valor_imovel:
            imovel.valor_leilao != null
              ? Number(imovel.valor_leilao)
              : null,
          observacoes: observacoes.trim() || null,
        }),
      });

      setOportunidade(dados);
      await carregarFluxo();
    } catch (error) {
      console.error("Erro ao criar oportunidade:", error);

      if (
        String(error.message).includes(
          "Já existe uma oportunidade ativa"
        )
      ) {
        setErro(
          "Este imóvel já possui uma oportunidade ativa. Acesse a oportunidade existente para continuar."
        );

        await carregarFluxo();
        return;
      }

      setErro(
        error.message ||
          "Não foi possível criar a oportunidade."
      );
    } finally {
      setSalvando(false);
    }
  }

  async function atualizarStatusOportunidade(status) {
    if (!oportunidade?.id) return;

    setSalvando(true);
    setErro("");

    try {
      await requisicao(`/oportunidades/${oportunidade.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await carregarFluxo();
    } catch (error) {
      console.error("Erro ao atualizar oportunidade:", error);
      setErro(error.message || "Não foi possível atualizar a oportunidade.");
    } finally {
      setSalvando(false);
    }
  }

  async function criarNegociacao() {
    if (!oportunidade?.id) return;

    setSalvando(true);
    setErro("");

    try {
      await requisicao("/negociacoes", {
        method: "POST",
        body: JSON.stringify({
          oportunidade_id: oportunidade.id,
          valor_proposto:
            valorProposto === "" ? null : Number(valorProposto),
          observacoes: observacaoNegociacao.trim() || null,
        }),
      });

      setValorProposto("");
      setObservacaoNegociacao("");
      await carregarFluxo();
    } catch (error) {
      console.error("Erro ao criar negociação:", error);
      setErro(error.message || "Não foi possível criar a negociação.");
    } finally {
      setSalvando(false);
    }
  }

  async function atualizarStatusNegociacao(negociacaoId, status) {
    setSalvando(true);
    setErro("");

    try {
      await requisicao(`/negociacoes/${negociacaoId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await carregarFluxo();
    } catch (error) {
      console.error("Erro ao atualizar negociação:", error);
      setErro(error.message || "Não foi possível atualizar a negociação.");
    } finally {
      setSalvando(false);
    }
  }

  async function enviarContraproposta() {
    if (!negociacaoAtual?.id) return;

    const valor = Number(
      String(valorContraproposta).replace(",", ".")
    );

    if (!Number.isFinite(valor) || valor <= 0) {
      setErro("Informe um valor válido para a contraproposta.");
      return;
    }

    try {
      setErro("");

      await requisicao(
        `/negociacoes/${negociacaoAtual.id}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: "contraproposta",
            valor_proposto: valor,
            observacoes:
              observacoesContraproposta.trim() || null,
          }),
        }
      );

      setMostrarContraproposta(false);
      setValorContraproposta("");
      setObservacoesContraproposta("");

      await carregarFluxo();

    } catch (error) {
      console.error("ERRO AO ENVIAR CONTRAPROPOSTA:", error);

      setErro(
        error.message ||
        "Não foi possível registrar a contraproposta."
      );
    }
  }

  async function criarOperacao() {
    if (!oportunidade?.id) return;

    const valor = Number(valorOperacao);

    if (!Number.isFinite(valor) || valor <= 0) {
      setErro("Informe um valor de imóvel maior que zero para criar a operação.");
      return;
    }

    setSalvando(true);
    setErro("");

    try {
      await requisicao("/operacoes", {
        method: "POST",
        body: JSON.stringify({
          oportunidade_id: oportunidade.id,
          valor_imovel: valor,
        }),
      });

      setValorOperacao("");
      await carregarFluxo();
    } catch (error) {
      console.error("Erro ao criar operação:", error);
      setErro(error.message || "Não foi possível criar a operação.");
    } finally {
      setSalvando(false);
    }
  }

  async function atualizarStatusOperacao(status) {
    if (!operacao?.id) return;

    setSalvando(true);
    setErro("");

    try {
      await requisicao(`/operacoes/${operacao.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      await carregarFluxo();
    } catch (error) {
      console.error("Erro ao atualizar operação:", error);
      setErro(error.message || "Não foi possível atualizar a operação.");
    } finally {
      setSalvando(false);
    }
  }

  const negociacaoAtual = negociacoes[0] || null;
  const podeCriarNegociacao =
    podeGerenciarNegociacao &&
    oportunidade &&
    !["concluida", "cancelada"].includes(oportunidade.status);

  const podeCriarOperacao =
    podeGerenciarOperacao && negociacaoAtual?.status === "aceita" && !operacao;

  return (
    <section className="oportunidade-panel">
      <div className="oportunidade-header">
        <div>
          <span className="oportunidade-kicker">
            <Handshake size={15} /> GESTÃO DA OPORTUNIDADE
          </span>
          <h3>Oportunidade</h3>
          <span className="oportunidade-role-badge">
            {ehAdministrador
              ? "Visão de administrador"
              : ehCorretor
                ? "Visão de corretor"
                : ehCliente
                  ? "Visão de cliente"
                  : "Papel não configurado"}
          </span>
        </div>

        <button
          type="button"
          className="oportunidade-refresh"
          onClick={carregarFluxo}
          disabled={carregando || salvando}
          aria-label="Atualizar oportunidade"
          title="Atualizar"
        >
          <RefreshCw size={16} className={carregando ? "spin" : ""} />
        </button>
      </div>

      {erro && (
        <div className="oportunidade-error">
          <CircleX size={17} />
          <span>{erro}</span>
        </div>
      )}

      {carregando ? (
        <div className="oportunidade-loading">
          <LoaderCircle size={20} className="spin" />
          <span>Carregando fluxo...</span>
        </div>
      ) : oportunidade ? (
        <>
          <div className="oportunidade-status-row">
            <div>
              <span>Status atual</span>
              <strong
                className={`oportunidade-status status-${oportunidade.status}`}
              >
                {STATUS_OPORTUNIDADE[oportunidade.status] || oportunidade.status}
              </strong>
            </div>

            <div>
              <span>Valor registrado</span>
              <strong>{dinheiro(oportunidade.valor_imovel)}</strong>
            </div>

            <div>
              <span>Criada em</span>
              <strong>{dataFormatada(oportunidade.criado_em)}</strong>
            </div>
          </div>

          {oportunidade.observacoes && (
            <div className="oportunidade-notes">
              <span>Observações</span>
              <p>{oportunidade.observacoes}</p>
            </div>
          )}

          {podeGerenciarOportunidade && <div className="oportunidade-actions">
            {!['em_contato', 'concluida', 'cancelada'].includes(oportunidade.status) && (
              <button
                type="button"
                onClick={() => atualizarStatusOportunidade("em_contato")}
                disabled={salvando}
              >
                Em contato
              </button>
            )}

            {!['negociando', 'concluida', 'cancelada'].includes(oportunidade.status) && (
              <button
                type="button"
                onClick={() => atualizarStatusOportunidade("negociando")}
                disabled={salvando}
              >
                Negociando
              </button>
            )}

            {!['concluida', 'cancelada'].includes(oportunidade.status) && (
              <button
                type="button"
                className="oportunidade-success"
                onClick={() => atualizarStatusOportunidade("concluida")}
                disabled={salvando}
              >
                <CircleCheck size={16} /> Concluir
              </button>
            )}

            {!['cancelada', 'concluida'].includes(oportunidade.status) && (
              <button
                type="button"
                className="oportunidade-danger"
                onClick={() => atualizarStatusOportunidade("cancelada")}
                disabled={salvando}
              >
                Cancelar
              </button>
            )}
          </div>}
          {ehCliente && (
            <p className="fluxo-readonly-note">
              Você pode acompanhar o andamento por aqui. As atualizações da oportunidade são feitas pelo corretor responsável ou administrador.
            </p>
          )}

          <div className="fluxo-section">
            <div className="fluxo-section-header">
              <div>
                <span className="fluxo-kicker">ETAPA 2</span>
                <h4>Negociação</h4>
              </div>
              {negociacaoAtual && (
                <span className={`fluxo-status status-negociacao-${negociacaoAtual.status}`}>
                  {STATUS_NEGOCIACAO[negociacaoAtual.status] || negociacaoAtual.status}
                </span>
              )}
            </div>

            {negociacaoAtual ? (
              <div className="fluxo-card">
                <div className="fluxo-grid">
                  <div>
                    <span>Valor proposto</span>
                    <strong>{dinheiro(negociacaoAtual.valor_proposto)}</strong>
                  </div>
                  <div>
                    <span>Criada em</span>
                    <strong>{dataFormatada(negociacaoAtual.criado_em)}</strong>
                  </div>
                </div>

                {negociacaoAtual.observacoes && (
                  <div className="fluxo-note">
                    <span>Observações</span>
                    <p>{negociacaoAtual.observacoes}</p>
                  </div>
                )}

                <div className="fluxo-actions">
                  {podeGerenciarNegociacao &&
                    negociacaoAtual.status !== "aceita" &&
                    negociacaoAtual.status !== "cancelada" &&
                    negociacaoAtual.status !== "recusada" && (
                      <>
                        <button
                          type="button"
                          onClick={() => {
                            setMostrarContraproposta(true);
                            setErro("");
                          }}
                        >
                          Contraproposta
                        </button>
                        <button
                          type="button"
                          className="oportunidade-success"
                          onClick={() => atualizarStatusNegociacao(negociacaoAtual.id, "aceita")}
                          disabled={salvando}
                        >
                          <CircleCheck size={16} /> Aceitar
                        </button>
                        <button
                          type="button"
                          className="oportunidade-danger"
                          onClick={() => atualizarStatusNegociacao(negociacaoAtual.id, "recusada")}
                          disabled={salvando}
                        >
                          Recusar
                        </button>
                      </>
                    )}
                </div>
                {ehCliente && (
                  <p className="fluxo-readonly-note">
                    Negociação em modo de consulta. O corretor responsável ou administrador registra as atualizações.
                  </p>
                )}
              </div>
            ) : podeCriarNegociacao ? (
              <div className="fluxo-form">
                <div className="fluxo-form-grid">
                  <label>
                    Valor proposto
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={valorProposto}
                      onChange={(event) => setValorProposto(event.target.value)}
                      placeholder="380000"
                    />
                  </label>

                  <label>
                    Observações
                    <textarea
                      rows={2}
                      value={observacaoNegociacao}
                      onChange={(event) => setObservacaoNegociacao(event.target.value)}
                      placeholder="Ex.: Cliente apresentou proposta inicial."
                    />
                  </label>
                </div>

                <button
                  type="button"
                  className="fluxo-primary"
                  onClick={criarNegociacao}
                  disabled={salvando}
                >
                  <Plus size={16} />
                  {salvando ? "Registrando..." : "Registrar negociação"}
                </button>
              </div>
            ) : ehCliente ? (
              <div className="fluxo-empty">
                A negociação será registrada pelo corretor responsável ou administrador após a análise do seu interesse.
              </div>
            ) : (
              <div className="fluxo-empty">
                A oportunidade está encerrada. Não é possível iniciar uma nova negociação.
              </div>
            )}
          </div>

          {mostrarContraproposta && podeGerenciarNegociacao && (
            <div className="contraproposta-form">
              <div className="contraproposta-form-titulo">
                Nova contraproposta
              </div>

              <label>
                Valor da contraproposta
              </label>

              <input
                type="number"
                min="0"
                step="0.01"
                value={valorContraproposta}
                onChange={(e) =>
                  setValorContraproposta(e.target.value)
                }
                placeholder="Ex.: 390000"
              />

              <label>
                Observações
              </label>

              <textarea
                value={observacoesContraproposta}
                onChange={(e) =>
                  setObservacoesContraproposta(e.target.value)
                }
                placeholder="Ex.: Cliente apresentou nova proposta."
                rows={3}
              />

              <div className="contraproposta-form-acoes">
                <button
                  type="button"
                  onClick={() => {
                    setMostrarContraproposta(false);
                    setValorContraproposta("");
                    setObservacoesContraproposta("");
                  }}
                >
                  Cancelar
                </button>

                <button
                  type="button"
                  onClick={() => {
                    enviarContraproposta();
                  }}
                >
                  Enviar contraproposta
                </button>
              </div>
            </div>
          )}    

          <div className="fluxo-section">
            <div className="fluxo-section-header">
              <div>
                <span className="fluxo-kicker">HISTÓRICO</span>
                <h4>Histórico da oportunidade</h4>
              </div>
            </div>

            <div className="fluxo-card">
              <div className="fluxo-history">
                <div className="fluxo-history-item">
                  <div>
                    <strong>Oportunidade criada</strong>
                    <span>{dataFormatada(oportunidade.criado_em)}</span>
                  </div>
                  <span className={`fluxo-status status-${oportunidade.status}`}>
                    {STATUS_OPORTUNIDADE[oportunidade.status] || oportunidade.status}
                  </span>
                </div>

                {negociacoes.length > 0 ? (
                  negociacoes
                    .slice()
                    .sort(
                      (a, b) =>
                        new Date(b.criado_em || 0).getTime() -
                        new Date(a.criado_em || 0).getTime()
                    )
                    .map((negociacao) => (
                      <div className="fluxo-history-item" key={`negociacao-${negociacao.id}`}>
                        <div>
                          <strong>Negociação registrada</strong>
                          <span>
                            {dataFormatada(negociacao.criado_em)}
                            {negociacao.valor_proposto != null
                              ? ` • ${dinheiro(negociacao.valor_proposto)}`
                              : " • Valor não informado"}
                          </span>
                        </div>
                        <span className={`fluxo-status status-negociacao-${negociacao.status}`}>
                          {STATUS_NEGOCIACAO[negociacao.status] || negociacao.status}
                        </span>
                      </div>
                    ))
                ) : (
                  <div className="fluxo-history-item">
                    <div>
                      <strong>Nenhuma negociação registrada</strong>
                      <span>A etapa de negociação ainda não foi iniciada.</span>
                    </div>
                  </div>
                )}

                {operacao ? (
                  <div className="fluxo-history-item">
                    <div>
                      <strong>Operação registrada</strong>
                      <span>
                        {dataFormatada(operacao.criado_em)} • {dinheiro(operacao.valor_imovel)}
                        {operacao.concluido_em
                          ? ` • Concluída em ${dataFormatada(operacao.concluido_em)}`
                          : ""}
                      </span>
                    </div>
                    <span className={`fluxo-status status-operacao-${operacao.status}`}>
                      {STATUS_OPERACAO[operacao.status] || operacao.status}
                    </span>
                  </div>
                ) : (
                  <div className="fluxo-history-item">
                    <div>
                      <strong>Operação ainda não registrada</strong>
                      <span>Será adicionada ao histórico quando for criada.</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="fluxo-section">
            <div className="fluxo-section-header">
              <div>
                <span className="fluxo-kicker">ETAPA 3</span>
                <h4>Operação</h4>
              </div>
              {operacao && (
                <span className={`fluxo-status status-operacao-${operacao.status}`}>
                  {STATUS_OPERACAO[operacao.status] || operacao.status}
                </span>
              )}
            </div>

            {operacao ? (
              <div className="fluxo-card">
                <div className="fluxo-grid fluxo-grid-3">
                  <div>
                    <span>Valor do imóvel</span>
                    <strong>{dinheiro(operacao.valor_imovel)}</strong>
                  </div>
                  <div>
                    <span>Taxa</span>
                    <strong>{operacao.percentual_taxa}%</strong>
                  </div>
                  <div>
                    <span>Valor da taxa</span>
                    <strong>{dinheiro(operacao.valor_taxa)}</strong>
                  </div>
                </div>

                <div className="fluxo-actions">
                  {podeGerenciarOperacao && operacao.status === "em_andamento" && (
                    <button
                      type="button"
                      className="oportunidade-success"
                      onClick={() => atualizarStatusOperacao("concluida")}
                      disabled={salvando}
                    >
                      <CircleCheck size={16} /> Concluir operação
                    </button>
                  )}
                  {podeGerenciarOperacao && operacao.status === "em_andamento" && (
                    <button
                      type="button"
                      className="oportunidade-danger"
                      onClick={() => atualizarStatusOperacao("cancelada")}
                      disabled={salvando}
                    >
                      Cancelar operação
                    </button>
                  )}
                </div>
                {!podeGerenciarOperacao && (
                  <p className="fluxo-readonly-note">
                    A operação está disponível para consulta. Ações de operação são feitas pelo corretor responsável ou administrador.
                  </p>
                )}
              </div>
            ) : podeCriarOperacao ? (
              <div className="fluxo-form">
                <div className="fluxo-operacao-intro">
                  <ArrowRight size={16} />
                  <span>Negociação aceita. Agora é possível iniciar a operação.</span>
                </div>

                <label>
                  Valor do imóvel na operação
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={valorOperacao}
                    onChange={(event) => setValorOperacao(event.target.value)}
                    placeholder={
                      negociacaoAtual?.valor_proposto != null
                        ? String(negociacaoAtual.valor_proposto)
                        : "380000"
                    }
                  />
                </label>

                <button
                  type="button"
                  className="fluxo-primary"
                  onClick={criarOperacao}
                  disabled={salvando}
                >
                  <Plus size={16} />
                  {salvando ? "Criando..." : "Criar operação"}
                </button>
              </div>
            ) : (
              <div className="fluxo-empty">
                {ehCliente
                  ? "A operação será iniciada pelo corretor responsável ou administrador após a negociação ser aceita."
                  : "A operação só pode ser criada depois que uma negociação for aceita."}
              </div>
            )}
          </div>
          {podeGerenciarOportunidade && (
            <SimuladorRentabilidade
              oportunidadeId={oportunidade.id}
              token={token}
              onCenarioSelecionado={onCenarioSelecionado}
              cenarioSelecionadoId={cenarioSelecionadoId}
            />
          )}
        </>
      ) : (
        <div className="oportunidade-empty">
          <div>
            <strong>Este imóvel ainda não possui uma oportunidade disponível para você.</strong>
            <span>
              {ehCorretor
                ? "O corretor acompanha oportunidades atribuídas a ele."
                : "Registre o interesse para começar a acompanhar este imóvel."}
            </span>
          </div>

          {(ehCliente || ehAdministrador) && (
            <>
              <label>
                Observações
                <textarea
                  value={observacoes}
                  onChange={(event) => setObservacoes(event.target.value)}
                  placeholder="Ex.: Cliente demonstrou interesse no imóvel."
                  rows={3}
                />
              </label>

              <button
                type="button"
                className="oportunidade-create"
                onClick={criarOportunidade}
                disabled={salvando}
              >
                <Plus size={17} />
                {salvando ? "Criando..." : "Criar oportunidade"}
              </button>
            </>
          )}
        </div>
      )}
    </section>
  );
}

export default Oportunidade;
