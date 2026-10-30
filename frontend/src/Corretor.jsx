import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Handshake,
  LoaderCircle,
  MessageSquare,
  RefreshCw,
} from "lucide-react";

import { API_URL } from "./api";

const SECOES_DASHBOARD = [
  { chave: "oportunidades", titulo: "Oportunidades" },
  { chave: "negociacoes", titulo: "Negociações" },
  { chave: "operacoes", titulo: "Operações" },
];

const STATUS_OPORTUNIDADE = {
  interesse: "Interesse",
  em_contato: "Em contato",
  negociando: "Negociando",
  concluida: "Concluída",
  cancelada: "Cancelada",
};

const STATUS_EDITAVEIS = Object.entries(STATUS_OPORTUNIDADE);

function dataFormatada(valor) {
  if (!valor) return "Não informada";
  const data = new Date(valor);
  return Number.isNaN(data.getTime())
    ? "Não informada"
    : data.toLocaleString("pt-BR");
}

const CANAIS_CONTATO = [
  ["telefone", "Telefone"],
  ["whatsapp", "WhatsApp"],
  ["email", "E-mail"],
  ["presencial", "Presencial"],
  ["outro", "Outro"],
];

const ROTULOS_ATIVIDADE = {
  contato: "Contato",
  nota: "Nota",
  status: "Mudança de status",
};

function rotuloOrigem(oportunidade) {
  if (oportunidade.anuncio_id != null) return `Anúncio do corretor #${oportunidade.anuncio_id}`;
  if (oportunidade.imovel_id != null) return `Imóvel da Caixa #${oportunidade.imovel_id}`;
  return "Origem não informada";
}

async function lerResposta(resposta) {
  try {
    return await resposta.json();
  } catch {
    return null;
  }
}

function IndicadorDashboard({ secao, destaque = false }) {
  const status = secao?.por_status;
  const entradas = status && typeof status === "object" && !Array.isArray(status)
    ? Object.entries(status)
    : [];
  const total = Number.isFinite(Number(secao?.total)) ? Number(secao.total) : 0;
  const somaStatus = entradas.reduce((soma, [, quantidade]) => {
    const valor = Number(quantidade);
    return soma + (Number.isFinite(valor) ? valor : 0);
  }, 0);
  const incompleto = !Number.isFinite(Number(secao?.total)) || !status || typeof status !== "object";

  return (
    <section className={`corretor-dashboard-card${destaque ? " is-highlighted" : ""}`}>
      <div className="corretor-dashboard-card-heading">
        <h3>{secao?.titulo}</h3>
        <strong className="corretor-dashboard-total">{total}</strong>
      </div>
      <span className="corretor-dashboard-total-label">Total</span>

      {entradas.length > 0 ? (
        <ul className="corretor-dashboard-status-list">
          {entradas.map(([nome, quantidade]) => {
            const valor = Number(quantidade);
            const quantidadeValida = Number.isFinite(valor) ? valor : 0;
            const percentual = somaStatus > 0
              ? Math.min(100, (quantidadeValida / somaStatus) * 100)
              : 0;

            return (
              <li key={nome} className="corretor-dashboard-status-item">
                <div className="corretor-dashboard-status-label">
                  <span>{nome}</span>
                  <strong>{quantidadeValida}</strong>
                </div>
                <span className="corretor-dashboard-track" aria-hidden="true">
                  <span style={{ width: `${percentual}%` }} />
                </span>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="corretor-dashboard-no-status">Nenhum status retornado.</p>
      )}

      {incompleto && (
        <p className="corretor-dashboard-incomplete">Alguns dados não vieram na resposta.</p>
      )}
    </section>
  );
}

function PainelIndicadores({ dashboard, loadingDashboard, erroDashboard, carregarDashboard }) {
  const faltando = dashboard && SECOES_DASHBOARD.some(({ chave }) => {
    const grupo = dashboard[chave];
    return !grupo || !Number.isFinite(Number(grupo.total)) || !grupo.por_status || typeof grupo.por_status !== "object";
  });

  return (
    <section className="corretor-dashboard" aria-labelledby="corretor-dashboard-titulo">
      <div className="corretor-dashboard-heading">
        <div>
          <span className="section-kicker">VISÃO GERAL</span>
          <h2 id="corretor-dashboard-titulo">Painel do Corretor</h2>
          <p>Veja o volume e o estágio das oportunidades sob sua responsabilidade.</p>
        </div>
        <button
          type="button"
          className="oportunidades-refresh"
          onClick={carregarDashboard}
          disabled={loadingDashboard}
          aria-label="Atualizar indicadores"
          title="Atualizar indicadores"
        >
          {loadingDashboard
            ? <LoaderCircle size={18} className="spin" />
            : <RefreshCw size={18} />}
        </button>
      </div>

      {erroDashboard && (
        <div className="oportunidades-error corretor-dashboard-message" role="alert">
          <AlertTriangle size={16} />
          <span>{erroDashboard}</span>
          <button type="button" onClick={carregarDashboard}>Tentar novamente</button>
        </div>
      )}

      {loadingDashboard && !dashboard ? (
        <div className="oportunidades-loading corretor-dashboard-loading">
          <LoaderCircle size={18} className="spin" /> Carregando indicadores...
        </div>
      ) : dashboard ? (
        <>
          {faltando && (
            <div className="corretor-dashboard-incomplete-banner" role="status">
              A API retornou dados incompletos. Os campos ausentes são exibidos como zero ou sem status.
            </div>
          )}
          <div className="corretor-dashboard-grid">
            {SECOES_DASHBOARD.map(({ chave, titulo }, indice) => (
              <IndicadorDashboard
                key={chave}
                destaque={indice === 0}
                secao={{ ...dashboard[chave], titulo }}
              />
            ))}
          </div>
        </>
      ) : !erroDashboard ? (
        <div className="corretor-dashboard-empty">Nenhum indicador disponível.</div>
      ) : null}
    </section>
  );
}

function Corretor({ usuario, token, onAbrirOportunidade }) {
  const [oportunidades, setOportunidades] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [erroDashboard, setErroDashboard] = useState("");
  const [dashboard, setDashboard] = useState(null);
  const [statusSelecionados, setStatusSelecionados] = useState({});
  const [salvandoStatusId, setSalvandoStatusId] = useState(null);
  const [erroStatus, setErroStatus] = useState("");
  const [historicos, setHistoricos] = useState({});
  const [historicoAberto, setHistoricoAberto] = useState({});
  const [rascunhosAtividade, setRascunhosAtividade] = useState({});
  const [salvandoAtividadeId, setSalvandoAtividadeId] = useState(null);
  const [erroAtividade, setErroAtividade] = useState({});

  const carregarHistorico = async (oportunidadeId) => {
    setErroAtividade((atuais) => ({ ...atuais, [oportunidadeId]: "" }));
    try {
      const resposta = await fetch(`${API_URL}/oportunidades/${oportunidadeId}/atividades`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const dados = await lerResposta(resposta);
      if (!resposta.ok) throw new Error(dados?.detail || `Não foi possível carregar o histórico (${resposta.status}).`);
      setHistoricos((atuais) => ({ ...atuais, [oportunidadeId]: Array.isArray(dados) ? dados : [] }));
    } catch (error) {
      setErroAtividade((atuais) => ({ ...atuais, [oportunidadeId]: error.message || "Erro ao carregar o histórico." }));
    }
  };

  const alternarHistorico = async (oportunidadeId) => {
    const abrir = !historicoAberto[oportunidadeId];
    setHistoricoAberto((atuais) => ({ ...atuais, [oportunidadeId]: abrir }));
    if (abrir && historicos[oportunidadeId] === undefined) await carregarHistorico(oportunidadeId);
  };

  const salvarAtividade = async (oportunidadeId) => {
    const rascunho = rascunhosAtividade[oportunidadeId] || {};
    setSalvandoAtividadeId(oportunidadeId);
    setErroAtividade((atuais) => ({ ...atuais, [oportunidadeId]: "" }));
    try {
      const resposta = await fetch(`${API_URL}/oportunidades/${oportunidadeId}/atividades`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ tipo: rascunho.tipo || "contato", canal: rascunho.canal || "telefone", descricao: rascunho.descricao || "" }),
      });
      const dados = await lerResposta(resposta);
      if (!resposta.ok) throw new Error(dados?.detail || `Não foi possível salvar a atividade (${resposta.status}).`);
      setHistoricos((atuais) => ({ ...atuais, [oportunidadeId]: [dados, ...(atuais[oportunidadeId] || [])] }));
      setRascunhosAtividade((atuais) => ({ ...atuais, [oportunidadeId]: { ...atuais[oportunidadeId], descricao: "" } }));
    } catch (error) {
      setErroAtividade((atuais) => ({ ...atuais, [oportunidadeId]: error.message || "Erro ao salvar a atividade." }));
    } finally {
      setSalvandoAtividadeId(null);
    }
  };

  const carregarOportunidades = useCallback(async () => {
    if (usuario?.tipo !== "corretor" || !usuario?.id || !token) {
      setOportunidades([]);
      setCarregando(false);
      return;
    }

    setCarregando(true);
    setErro("");
    try {
      const resposta = await fetch(
        `${API_URL}/oportunidades/corretor/${usuario.id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const dados = await lerResposta(resposta);
      if (!resposta.ok) {
        throw new Error(dados?.detail || `Não foi possível carregar as oportunidades (${resposta.status}).`);
      }
      setOportunidades(Array.isArray(dados) ? dados : []);
    } catch (error) {
      setErro(error.message || "Erro ao carregar oportunidades.");
    } finally {
      setCarregando(false);
    }
  }, [usuario?.id, usuario?.tipo, token]);

  const carregarDashboard = useCallback(async () => {
    if (usuario?.tipo !== "corretor" || !usuario?.id || !token) {
      setDashboard(null);
      setLoadingDashboard(false);
      setErroDashboard("");
      return;
    }

    setLoadingDashboard(true);
    setErroDashboard("");
    try {
      const resposta = await fetch(
        `${API_URL}/oportunidades/corretor/${usuario.id}/dashboard`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const dados = await lerResposta(resposta);
      if (!resposta.ok) {
        throw new Error(dados?.detail || `Não foi possível carregar o dashboard (${resposta.status}).`);
      }
      setDashboard(dados && typeof dados === "object" && !Array.isArray(dados) ? dados : {});
    } catch (error) {
      setErroDashboard(error.message || "Erro ao carregar os indicadores.");
    } finally {
      setLoadingDashboard(false);
    }
  }, [usuario?.id, usuario?.tipo, token]);

  const atualizarStatus = async (oportunidade) => {
    const status = statusSelecionados[oportunidade.id] || oportunidade.status;
    if (!status || status === oportunidade.status) return;

    setSalvandoStatusId(oportunidade.id);
    setErroStatus("");
    try {
      const resposta = await fetch(`${API_URL}/oportunidades/${oportunidade.id}/status`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status }),
      });
      const dados = await lerResposta(resposta);
      if (!resposta.ok) {
        throw new Error(dados?.detail || `Não foi possível atualizar o status (${resposta.status}).`);
      }
      setOportunidades((atuais) => atuais.map((item) => item.id === oportunidade.id ? dados : item));
      if (historicos[oportunidade.id] !== undefined) await carregarHistorico(oportunidade.id);
      await carregarDashboard();
      setStatusSelecionados((atuais) => {
        const novos = { ...atuais };
        delete novos[oportunidade.id];
        return novos;
      });
    } catch (error) {
      setErroStatus(error.message || "Erro ao atualizar o status.");
    } finally {
      setSalvandoStatusId(null);
    }
  };

  useEffect(() => {
    if (usuario?.tipo !== "corretor") return;
    carregarOportunidades();
    carregarDashboard();
  }, [usuario?.tipo, carregarOportunidades, carregarDashboard]);

  if (usuario?.tipo !== "corretor") return null;

  return (
    <section id="painel-corretor" className="minhas-oportunidades painel-corretor">
      <PainelIndicadores
        dashboard={dashboard}
        loadingDashboard={loadingDashboard}
        erroDashboard={erroDashboard}
        carregarDashboard={carregarDashboard}
      />

      <div className="corretor-opportunities-section">
        <div className="oportunidades-header">
          <div>
            <span className="section-kicker">CARTEIRA ATRIBUÍDA</span>
            <h2>Minhas oportunidades</h2>
            <p>Acompanhe imóveis, negociações e operações atribuídos a você.</p>
          </div>
          <button type="button" className="oportunidades-refresh" onClick={carregarOportunidades} disabled={carregando} aria-label="Atualizar oportunidades" title="Atualizar">
            <RefreshCw size={18} className={carregando ? "spin" : ""} />
          </button>
        </div>

        {erro && <div className="oportunidades-error" role="alert"><AlertTriangle size={16} /> {erro}</div>}
        {erroStatus && <div className="oportunidades-error" role="alert"><AlertTriangle size={16} /> {erroStatus}</div>}

        {carregando ? (
          <div className="oportunidades-loading"><LoaderCircle size={18} className="spin" /> Carregando oportunidades...</div>
        ) : !erro && oportunidades.length === 0 ? (
          <div className="oportunidades-empty">
            <Handshake size={32} />
            <strong>Nenhuma oportunidade atribuída</strong>
            <span>Quando uma oportunidade for atribuída a você, ela aparecerá aqui.</span>
          </div>
        ) : (
          <div className="oportunidades-lista">
            {oportunidades.map((oportunidade) => (
              <article key={oportunidade.id} className="oportunidade-item">
                <div className="oportunidade-item-topo">
                  <div className="oportunidade-item-titulo">
                    <strong>Oportunidade #{oportunidade.id}</strong>
                    <span>{rotuloOrigem(oportunidade)}</span>
                  </div>
                  <span className={`oportunidade-status ${String(oportunidade.status || "").replaceAll("_", "-")}`}>
                    {STATUS_OPORTUNIDADE[oportunidade.status] || oportunidade.status || "Sem status"}
                  </span>
                </div>
                <div className="oportunidade-item-dados">
                  <div><span>Cliente</span><strong>{oportunidade.cliente_id != null ? `#${oportunidade.cliente_id}` : "Não informado"}</strong></div>
                  {oportunidade.valor_imovel != null && <div><span>Valor informado</span><strong>{Number(oportunidade.valor_imovel).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}</strong></div>}
                  <div><span>Criada em</span><strong>{dataFormatada(oportunidade.criado_em)}</strong></div>
                  <div><span>Atualizada em</span><strong>{dataFormatada(oportunidade.atualizado_em)}</strong></div>
                </div>
                {oportunidade.observacoes && <p className="oportunidade-observacao">{oportunidade.observacoes}</p>}
                <div className="oportunidade-item-acoes">
                  <label className="corretor-status-edit">
                    Status comercial
                    <select
                      aria-label={`Status comercial da oportunidade ${oportunidade.id}`}
                      value={statusSelecionados[oportunidade.id] ?? oportunidade.status}
                      onChange={(evento) => setStatusSelecionados((atuais) => ({ ...atuais, [oportunidade.id]: evento.target.value }))}
                      disabled={salvandoStatusId === oportunidade.id}
                    >
                      {STATUS_EDITAVEIS.map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}
                    </select>
                    <button
                      type="button"
                      className="corretor-status-save"
                      onClick={() => atualizarStatus(oportunidade)}
                      disabled={salvandoStatusId === oportunidade.id || (statusSelecionados[oportunidade.id] ?? oportunidade.status) === oportunidade.status}
                    >
                      {salvandoStatusId === oportunidade.id ? "Salvando..." : "Salvar status"}
                    </button>
                  </label>
                  <button type="button" onClick={() => onAbrirOportunidade(oportunidade)}>
                    <ArrowRight size={15} /> Acompanhar oportunidade
                  </button>
                  <button type="button" onClick={() => alternarHistorico(oportunidade.id)} aria-expanded={Boolean(historicoAberto[oportunidade.id])}>
                    <MessageSquare size={15} /> {historicoAberto[oportunidade.id] ? "Ocultar histórico" : "Atividades e histórico"}
                  </button>
                </div>
                {historicoAberto[oportunidade.id] && (
                  <section className="corretor-atividade" aria-label={`Atividades da oportunidade ${oportunidade.id}`}>
                    <h3>Histórico comercial</h3>
                    <div className="corretor-atividade-form">
                      <label>Tipo de atividade
                        <select value={rascunhosAtividade[oportunidade.id]?.tipo || "contato"} onChange={(evento) => setRascunhosAtividade((atuais) => ({ ...atuais, [oportunidade.id]: { tipo: evento.target.value, canal: "telefone", descricao: atuais[oportunidade.id]?.descricao || "" } }))}>
                          <option value="contato">Contato realizado</option>
                          <option value="nota">Nota</option>
                        </select>
                      </label>
                      {(rascunhosAtividade[oportunidade.id]?.tipo || "contato") === "contato" && (
                        <label>Canal
                          <select value={rascunhosAtividade[oportunidade.id]?.canal || "telefone"} onChange={(evento) => setRascunhosAtividade((atuais) => ({ ...atuais, [oportunidade.id]: { ...atuais[oportunidade.id], canal: evento.target.value } }))}>
                            {CANAIS_CONTATO.map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}
                          </select>
                        </label>
                      )}
                      <label>Descrição
                        <textarea maxLength={5000} value={rascunhosAtividade[oportunidade.id]?.descricao || ""} onChange={(evento) => setRascunhosAtividade((atuais) => ({ ...atuais, [oportunidade.id]: { tipo: atuais[oportunidade.id]?.tipo || "contato", canal: atuais[oportunidade.id]?.canal || "telefone", descricao: evento.target.value } }))} placeholder="Registre o contato ou escreva uma nota..." />
                      </label>
                      <button type="button" className="corretor-atividade-save" onClick={() => salvarAtividade(oportunidade.id)} disabled={salvandoAtividadeId === oportunidade.id || !(rascunhosAtividade[oportunidade.id]?.descricao || "").trim()}>
                        {salvandoAtividadeId === oportunidade.id ? "Salvando..." : "Registrar atividade"}
                      </button>
                    </div>
                    {erroAtividade[oportunidade.id] && <p className="corretor-atividade-error" role="alert">{erroAtividade[oportunidade.id]}</p>}
                    {historicos[oportunidade.id] === undefined && !erroAtividade[oportunidade.id] ? <p className="corretor-atividade-empty">Carregando histórico...</p> : historicos[oportunidade.id]?.length === 0 ? <p className="corretor-atividade-empty">Nenhuma atividade registrada.</p> : historicos[oportunidade.id] && (
                      <ol className="corretor-atividade-lista">
                        {historicos[oportunidade.id].map((atividade) => (
                          <li key={atividade.id} className={`corretor-atividade-item ${atividade.tipo}`}>
                            <div><strong>{ROTULOS_ATIVIDADE[atividade.tipo] || atividade.tipo}{atividade.canal ? ` · ${CANAIS_CONTATO.find(([valor]) => valor === atividade.canal)?.[1] || atividade.canal}` : ""}</strong><time>{dataFormatada(atividade.criado_em)}</time></div>
                            {atividade.tipo === "status" ? <p>{STATUS_OPORTUNIDADE[atividade.status_anterior] || atividade.status_anterior} → {STATUS_OPORTUNIDADE[atividade.status_novo] || atividade.status_novo}</p> : <p>{atividade.descricao}</p>}
                          </li>
                        ))}
                      </ol>
                    )}
                  </section>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

export default Corretor;
