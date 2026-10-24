import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Handshake,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const STATUS = {
  interesse: {
    label: "Interesse",
    classe: "interesse",
  },
  em_contato: {
    label: "Em contato",
    classe: "em-contato",
  },
  negociando: {
    label: "Negociando",
    classe: "negociando",
  },
  concluida: {
    label: "Concluída",
    classe: "concluida",
  },
  cancelada: {
    label: "Cancelada",
    classe: "cancelada",
  },
};

function dinheiro(valor) {
  if (valor === null || valor === undefined || valor === "") {
    return "Não informado";
  }

  const numero = Number(valor);

  if (!Number.isFinite(numero)) {
    return "Não informado";
  }

  return numero.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function dataFormatada(valor) {
  if (!valor) return "Não informada";

  const data = new Date(valor);

  if (Number.isNaN(data.getTime())) {
    return "Não informada";
  }

  return data.toLocaleDateString("pt-BR");
}

const SECOES_DASHBOARD = [
  { chave: "oportunidades", titulo: "Oportunidades" },
  { chave: "negociacoes", titulo: "Negociações" },
  { chave: "operacoes", titulo: "Operações" },
];

async function lerJson(resposta) {
  try {
    return await resposta.json();
  } catch {
    return null;
  }
}

function IndicadorCliente({ titulo, dados }) {
  const estados = dados?.por_status;
  const porStatus = estados && typeof estados === "object" && !Array.isArray(estados)
    ? Object.entries(estados)
    : [];
  const totalValido = dados?.total !== null && dados?.total !== undefined && dados?.total !== "" && Number.isFinite(Number(dados.total));
  const total = totalValido ? Number(dados.total) : 0;
  const somaStatus = porStatus.reduce((soma, [, valor]) => {
    const numero = Number(valor);
    return soma + (Number.isFinite(numero) ? numero : 0);
  }, 0);
  const incompleto = !totalValido || !estados || typeof estados !== "object";

  return (
    <section className={`corretor-dashboard-card${titulo === "Oportunidades" ? " is-highlighted" : ""}`}>
      <div className="corretor-dashboard-card-heading">
        <h3>{titulo}</h3>
        <strong className="corretor-dashboard-total">{total}</strong>
      </div>
      <span className="corretor-dashboard-total-label">Total</span>
      {porStatus.length ? (
        <ul className="corretor-dashboard-status-list">
          {porStatus.map(([status, valor]) => {
            const quantidade = Number(valor);
            const quantidadeValida = Number.isFinite(quantidade) ? quantidade : 0;
            const percentual = somaStatus > 0 ? Math.min(100, (quantidadeValida / somaStatus) * 100) : 0;
            return (
              <li key={status} className="corretor-dashboard-status-item">
                <div className="corretor-dashboard-status-label">
                  <span>{status}</span>
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
      {incompleto && <p className="corretor-dashboard-incomplete">Alguns dados não vieram na resposta.</p>}
    </section>
  );
}

function MinhasOportunidades({ usuario, token, onAbrirImovel }) {
  const [oportunidades, setOportunidades] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [erroDashboard, setErroDashboard] = useState("");
  const [dashboard, setDashboard] = useState(null);

  const carregar = useCallback(async () => {
    if (usuario?.tipo !== "cliente" || !usuario?.id || !token) {
      setOportunidades([]);
      setCarregando(false);
      return;
    }

    setCarregando(true);
    setErro("");

    try {
      const resposta = await fetch(
        `${API_URL}/oportunidades/cliente/${usuario.id}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const dados = await lerJson(resposta);

      if (!resposta.ok) {
        throw new Error(
          dados?.detail ||
            "Não foi possível carregar as oportunidades."
        );
      }

      setOportunidades(Array.isArray(dados) ? dados : []);
    } catch (error) {
      setErro(
        error.message || "Erro ao carregar oportunidades."
      );
    } finally {
      setCarregando(false);
    }
  }, [usuario?.id, usuario?.tipo, token]);

  const carregarDashboard = useCallback(async () => {
    if (usuario?.tipo !== "cliente" || !usuario?.id || !token) {
      setDashboard(null);
      setErroDashboard("");
      setLoadingDashboard(false);
      return;
    }

    setLoadingDashboard(true);
    setErroDashboard("");
    try {
      const resposta = await fetch(
        `${API_URL}/oportunidades/cliente/${usuario.id}/dashboard`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const dados = await lerJson(resposta);
      if (!resposta.ok) {
        throw new Error(dados?.detail || `Não foi possível carregar o painel (${resposta.status}).`);
      }
      setDashboard(dados && typeof dados === "object" && !Array.isArray(dados) ? dados : {});
    } catch (error) {
      setErroDashboard(error.message || "Erro ao carregar os indicadores do cliente.");
    } finally {
      setLoadingDashboard(false);
    }
  }, [usuario?.id, usuario?.tipo, token]);

  useEffect(() => {
    carregar();
    carregarDashboard();
  }, [carregar, carregarDashboard]);

  if (usuario?.tipo !== "cliente") return null;

  const dashboardIncompleto = dashboard && SECOES_DASHBOARD.some(({ chave }) => {
    const grupo = dashboard[chave];
    return !grupo || grupo.total === null || grupo.total === undefined || grupo.total === "" ||
      !Number.isFinite(Number(grupo.total)) || !grupo.por_status || typeof grupo.por_status !== "object";
  });

  return (
    <section id="minhas-oportunidades" className="minhas-oportunidades">
      <section className="corretor-dashboard cliente-dashboard" aria-labelledby="cliente-dashboard-titulo">
        <div className="corretor-dashboard-heading">
          <div>
            <span className="section-kicker">ACOMPANHAMENTO</span>
            <h2 id="cliente-dashboard-titulo">Painel do Cliente</h2>
            <p>Consulte rapidamente as etapas das suas oportunidades, negociações e operações.</p>
          </div>
          <button
            type="button"
            className="oportunidades-refresh"
            onClick={carregarDashboard}
            disabled={loadingDashboard}
            aria-label="Atualizar indicadores"
            title="Atualizar indicadores"
          >
            {loadingDashboard ? <LoaderCircle size={18} className="spin" /> : <RefreshCw size={18} />}
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
            {dashboardIncompleto && (
              <div className="corretor-dashboard-incomplete-banner" role="status">
                A API retornou dados incompletos. Campos ausentes aparecem como zero ou sem status.
              </div>
            )}
            <div className="corretor-dashboard-grid">
              {SECOES_DASHBOARD.map(({ chave, titulo }) => (
                <IndicadorCliente key={chave} titulo={titulo} dados={dashboard[chave]} />
              ))}
            </div>
          </>
        ) : !erroDashboard ? (
          <div className="corretor-dashboard-empty">Nenhum indicador disponível.</div>
        ) : null}
      </section>

      <div className="oportunidades-header">
        <div>
          <span className="section-kicker">
            GESTÃO
          </span>

          <h2>Minhas oportunidades</h2>

          <p>
            Acompanhe seus imóveis, negociações e operações.
          </p>
        </div>

        <button
          type="button"
          className="oportunidades-refresh"
          onClick={carregar}
          title="Atualizar"
          aria-label="Atualizar oportunidades"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      {erro && (
        <div className="oportunidades-error">
          {erro}
        </div>
      )}

      {carregando && (
        <div className="oportunidades-loading">
          <RefreshCw size={18} className="spin" />
          Carregando oportunidades...
        </div>
      )}

      {!carregando && !erro && oportunidades.length === 0 && (
        <div className="oportunidades-empty">
          <Handshake size={32} />

          <strong>
            Nenhuma oportunidade encontrada
          </strong>

          <span>
            Quando você demonstrar interesse em um imóvel,
            ele aparecerá aqui.
          </span>
        </div>
      )}

      {!carregando && !erro && <div className="oportunidades-lista">
        {oportunidades.map((oportunidade) => {
          const status =
            STATUS[oportunidade.status] || {
              label: oportunidade.status || "Sem status",
              classe: "",
            };

          return (
            <article
              key={oportunidade.id}
              className="oportunidade-item"
            >
              <div className="oportunidade-item-topo">
                <div className="oportunidade-item-titulo">
                  <span>
                    Oportunidade #{oportunidade.id}
                  </span>

                  <strong>
                    Imóvel #{oportunidade.imovel_id}
                  </strong>
                </div>

                <span
                  className={`oportunidade-status ${status.classe}`}
                >
                  {status.label}
                </span>
              </div>

              <div className="oportunidade-item-dados">
                <div>
                  <small>Valor registrado</small>

                  <strong>
                    {dinheiro(oportunidade.valor_imovel)}
                  </strong>
                </div>

                <div>
                  <small>Criada em</small>

                  <strong>
                    {dataFormatada(
                      oportunidade.criado_em
                    )}
                  </strong>
                </div>

                <div>
                  <small>Atualizada em</small>

                  <strong>
                    {dataFormatada(
                      oportunidade.atualizado_em
                    )}
                  </strong>
                </div>
              </div>

              {oportunidade.observacoes && (
                <div className="oportunidade-observacao">
                  {oportunidade.observacoes}
                </div>
              )}

              <div className="oportunidade-item-acoes">
                <button
                  type="button"
                  onClick={() =>
                    onAbrirImovel?.(
                      oportunidade.imovel_id
                    )
                  }
                >
                  Acompanhar oportunidade
                  <ArrowRight size={16} />
                </button>
              </div>
            </article>
          );
        })}
      </div>}
    </section>
  );
}

export default MinhasOportunidades;
