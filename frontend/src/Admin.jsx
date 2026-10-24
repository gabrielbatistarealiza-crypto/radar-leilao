import { useEffect, useRef, useState } from "react";
import {
  LIMITE_POR_PEDIDO,
  aguardarComParagem,
  avaliarLote,
  intervaloDoStatus,
} from "./ritmoEnriquecimentoCaixa";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const CURSOR_ENRIQUECIMENTO_CAIXA = "radar-caixa-datas-cursor";

const formatarNumero = (valor) =>
  Number(valor || 0).toLocaleString("pt-BR");

function normalizarDashboard(resposta) {
  let incompleto = !resposta || typeof resposta !== "object";

  function numero(objeto, campo) {
    const valor = objeto?.[campo];
    if (valor === null || valor === undefined || valor === "" || !Number.isFinite(Number(valor))) {
      incompleto = true;
      return 0;
    }
    return Number(valor);
  }

  return {
    incompleto,
    dados: {
      imoveis: {
        total: numero(resposta?.imoveis, "total"),
        ativos: numero(resposta?.imoveis, "ativos"),
        encerrados: numero(resposta?.imoveis, "encerrados"),
      },
      fotos: {
        imoveis_com_fotos: numero(resposta?.fotos, "imoveis_com_fotos"),
        total_imagens: numero(resposta?.fotos, "total_imagens"),
      },
      usuarios: {
        total: numero(resposta?.usuarios, "total"),
        clientes: numero(resposta?.usuarios, "clientes"),
        corretores: numero(resposta?.usuarios, "corretores"),
        administradores: numero(resposta?.usuarios, "administradores"),
      },
      oportunidades: {
        total: numero(resposta?.oportunidades, "total"),
        interesse: numero(resposta?.oportunidades, "interesse"),
        em_contato: numero(resposta?.oportunidades, "em_contato"),
        negociando: numero(resposta?.oportunidades, "negociando"),
        concluida: numero(resposta?.oportunidades, "concluida"),
        cancelada: numero(resposta?.oportunidades, "cancelada"),
      },
      negociacoes: {
        total: numero(resposta?.negociacoes, "total"),
        abertas: numero(resposta?.negociacoes, "abertas"),
        contrapropostas: numero(resposta?.negociacoes, "contrapropostas"),
        aceitas: numero(resposta?.negociacoes, "aceitas"),
        recusadas: numero(resposta?.negociacoes, "recusadas"),
        canceladas: numero(resposta?.negociacoes, "canceladas"),
      },
      operacoes: {
        total: numero(resposta?.operacoes, "total"),
        em_andamento: numero(resposta?.operacoes, "em_andamento"),
        concluida: numero(resposta?.operacoes, "concluida"),
        cancelada: numero(resposta?.operacoes, "cancelada"),
      },
    },
  };
}

function Indicador({ rotulo, valor, destaque = false }) {
  return (
    <article className={`admin-metric-card${destaque ? " is-highlighted" : ""}`}>
      <span>{rotulo}</span>
      <strong>{formatarNumero(valor)}</strong>
    </article>
  );
}

function SecaoIndicadores({ titulo, legenda, itens }) {
  return (
    <section className="admin-metric-section">
      <div className="admin-metric-heading">
        <span>{legenda}</span>
        <h2>{titulo}</h2>
      </div>
      <div className="admin-metric-grid">
        {itens.map(([rotulo, valor], indice) => (
          <Indicador
            key={rotulo}
            rotulo={rotulo}
            valor={valor}
            destaque={indice === 0}
          />
        ))}
      </div>
    </section>
  );
}

function Admin({ usuario, onLogout }) {
  const [dashboard, setDashboard] = useState(null);
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [erroDashboard, setErroDashboard] = useState("");
  const [dashboardIncompleto, setDashboardIncompleto] = useState(false);
  const [usuarios, setUsuarios] = useState([]);
  const [oportunidadesSemCorretor, setOportunidadesSemCorretor] = useState([]);
  const [corretoresSelecionados, setCorretoresSelecionados] = useState({});
  const [erroAtribuicao, setErroAtribuicao] = useState("");
  const [atribuindoId, setAtribuindoId] = useState(null);
  const [carregandoUsuarios, setCarregandoUsuarios] = useState(true);
  const [erroUsuarios, setErroUsuarios] = useState("");
  const [mostrarNovo, setMostrarNovo] = useState(false);
  const [enriquecimentoCaixa, setEnriquecimentoCaixa] = useState({
    executando: false,
    processados: 0,
    atualizados: 0,
    semDadosNovos: 0,
    erros: 0,
    mensagem: "",
    cursor: localStorage.getItem(CURSOR_ENRIQUECIMENTO_CAIXA) || "",
  });
  const [statusWorkerDatasCaixa, setStatusWorkerDatasCaixa] = useState(null);
  const pararEnriquecimentoCaixa = useRef(false);

  const [novoNome, setNovoNome] = useState("");
  const [novoEmail, setNovoEmail] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [novoTipo, setNovoTipo] = useState("cliente");
  const [criando, setCriando] = useState(false);

  const [editandoId, setEditandoId] = useState(null);
  const [editNome, setEditNome] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editSenha, setEditSenha] = useState("");
  const [salvando, setSalvando] = useState(false);

  const token = localStorage.getItem("radar-leilao-token");

  async function carregarStatusWorkerDatasCaixa() {
    if (!token) return;
    try {
      const resposta = await fetch(`${API_URL}/caixa/enriquecer-datas/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resposta.ok) return;
      setStatusWorkerDatasCaixa(await resposta.json());
    } catch (error) {
      console.error("Não foi possível consultar o worker de datas da CAIXA.", error);
    }
  }

  async function carregarDashboard() {
    try {
      setLoadingDashboard(true);
      setErroDashboard("");

      const resposta = await fetch(`${API_URL}/admin/dashboard`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!resposta.ok) {
        const corpo = await resposta.json().catch(() => ({}));
        throw new Error(
          corpo.detail || "Não foi possível carregar o dashboard."
        );
      }

      const normalizado = normalizarDashboard(await resposta.json().catch(() => null));
      setDashboard(normalizado.dados);
      setDashboardIncompleto(normalizado.incompleto);
    } catch (error) {
      console.error(error);
      setErroDashboard(error.message || "Não foi possível carregar o dashboard.");
    } finally {
      setLoadingDashboard(false);
    }
  }

  async function carregarUsuarios() {
    try {
      setCarregandoUsuarios(true);
      setErroUsuarios("");

      const resposta = await fetch(`${API_URL}/admin/usuarios`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!resposta.ok) {
        const corpo = await resposta.json().catch(() => ({}));
        throw new Error(
          corpo.detail || "Não foi possível carregar os usuários."
        );
      }

      setUsuarios(await resposta.json());
    } catch (error) {
      console.error(error);
      setErroUsuarios(error.message);
    } finally {
      setCarregandoUsuarios(false);
    }
  }

  async function carregarOportunidadesSemCorretor() {
    try {
      setErroAtribuicao("");
      const resposta = await fetch(`${API_URL}/admin/oportunidades/sem-corretor`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const corpo = await resposta.json().catch(() => []);
      if (!resposta.ok) throw new Error(corpo.detail || "Não foi possível carregar oportunidades sem corretor.");
      setOportunidadesSemCorretor(Array.isArray(corpo) ? corpo : []);
    } catch (error) {
      setErroAtribuicao(error.message || "Erro ao carregar oportunidades.");
    }
  }

  async function enriquecerDatasCaixa() {
    if (!token || enriquecimentoCaixa.executando) return;

    // Mesmo ritmo do worker automático, lido do backend.
    let intervaloSegundos = intervaloDoStatus(statusWorkerDatasCaixa);
    try {
      const respostaStatus = await fetch(`${API_URL}/caixa/enriquecer-datas/status`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (respostaStatus.ok) {
        intervaloSegundos = intervaloDoStatus(await respostaStatus.json());
      }
    } catch {
      // Sem status: fica o intervalo padrão.
    }

    const confirmar = window.confirm(
      `Iniciar a busca das datas dos imóveis da CAIXA? Ela consultará ${LIMITE_POR_PEDIDO} imóvel de cada vez, com ${intervaloSegundos} s entre consultas, e salvará as datas encontradas. Pode pedir para parar a qualquer momento.`
    );
    if (!confirmar) return;

    pararEnriquecimentoCaixa.current = false;
    let cursor = Number(
      localStorage.getItem(CURSOR_ENRIQUECIMENTO_CAIXA)
    ) || null;

    setEnriquecimentoCaixa({
      executando: true,
      processados: 0,
      atualizados: 0,
      semDadosNovos: 0,
      erros: 0,
      mensagem: cursor
        ? `Retomando após o imóvel ${formatarNumero(cursor)}...`
        : "Iniciando a busca...",
      cursor: cursor ? String(cursor) : "",
    });

    let pausadoPorErro = false;
    let pausadoPorBloqueio = false;
    try {
      while (!pararEnriquecimentoCaixa.current) {
        const parametros = new URLSearchParams({ limite: String(LIMITE_POR_PEDIDO) });
        if (cursor) parametros.set("depois_id", String(cursor));

        const resposta = await fetch(
          `${API_URL}/caixa/enriquecer-datas?${parametros.toString()}`,
          {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        const resultado = await resposta.json().catch(() => ({}));
        if (!resposta.ok) {
          throw new Error(
            resultado.detail || "Não foi possível consultar as datas da CAIXA."
          );
        }

        const errosDoLote = Number(resultado.erros || 0);
        // Bloqueio, falha técnica ou erro deixam a retomada antes do imóvel.
        const { proximoCursor, pausa, fim } = avaliarLote(resultado);

        if (proximoCursor) {
          localStorage.setItem(
            CURSOR_ENRIQUECIMENTO_CAIXA,
            String(proximoCursor)
          );
        } else {
          localStorage.removeItem(CURSOR_ENRIQUECIMENTO_CAIXA);
        }
        cursor = proximoCursor;

        setEnriquecimentoCaixa((estado) => ({
          ...estado,
          processados: estado.processados + Number(resultado.processados || 0),
          atualizados: estado.atualizados + Number(resultado.atualizados || 0),
          semDadosNovos:
            estado.semDadosNovos + Number(resultado.sem_dados_novos || 0),
          erros: estado.erros + errosDoLote,
          cursor: cursor ? String(cursor) : "",
          mensagem:
            pausa === "bloqueio"
              ? "A CAIXA bloqueou temporariamente a consulta. Busca pausada; aguarde antes de retomar."
              : pausa === "falha_tecnica"
              ? "Não foi possível ler a página da CAIXA (falha técnica). Busca pausada; o imóvel será tentado de novo ao retomar."
              : pausa === "erro"
              ? "Pausado por erro. Corrija ou confira o imóvel indicado e depois retome."
              : "Imóvel concluído.",
        }));

        if (pausa === "bloqueio") {
          pausadoPorBloqueio = true;
          break;
        }

        if (pausa) {
          pausadoPorErro = true;
          break;
        }

        if (fim) {
          localStorage.removeItem(CURSOR_ENRIQUECIMENTO_CAIXA);
          setEnriquecimentoCaixa((estado) => ({
            ...estado,
            executando: false,
            cursor: "",
            mensagem: "Busca concluída: não há mais imóveis pendentes.",
          }));
          return;
        }

        // Mesma pausa do worker automático; a paragem é verificada a cada segundo.
        const parado = await aguardarComParagem(
          intervaloSegundos,
          () => pararEnriquecimentoCaixa.current,
          {
            aoTic: (restante) =>
              setEnriquecimentoCaixa((estado) => ({
                ...estado,
                mensagem: `Próxima consulta em ${restante} s.`,
              })),
          }
        );
        if (parado) break;
      }

      if (pausadoPorErro || pausadoPorBloqueio) {
        setEnriquecimentoCaixa((estado) => ({ ...estado, executando: false }));
      } else {
        setEnriquecimentoCaixa((estado) => ({
          ...estado,
          executando: false,
          mensagem: "Busca pausada. Você pode retomá-la quando quiser.",
        }));
      }
    } catch (error) {
      setEnriquecimentoCaixa((estado) => ({
        ...estado,
        executando: false,
        mensagem: error.message || "A busca foi interrompida por um erro.",
      }));
    }
  }

  function solicitarParadaEnriquecimentoCaixa() {
    pararEnriquecimentoCaixa.current = true;
    setEnriquecimentoCaixa((estado) => ({
      ...estado,
      mensagem: "Parada solicitada; a consulta em andamento será concluída.",
    }));
  }

  async function atribuirOportunidade(oportunidadeId) {
    const corretorId = corretoresSelecionados[oportunidadeId];
    if (!corretorId) return;
    setAtribuindoId(oportunidadeId);
    setErroAtribuicao("");
    try {
      const resposta = await fetch(`${API_URL}/admin/oportunidades/${oportunidadeId}/corretor`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ corretor_id: Number(corretorId) }),
      });
      const corpo = await resposta.json().catch(() => ({}));
      if (!resposta.ok) throw new Error(corpo.detail || "Não foi possível atribuir a oportunidade.");
      setOportunidadesSemCorretor((itens) => itens.filter((item) => item.id !== oportunidadeId));
      setCorretoresSelecionados((itens) => { const novos = { ...itens }; delete novos[oportunidadeId]; return novos; });
    } catch (error) {
      setErroAtribuicao(error.message || "Erro ao atribuir oportunidade.");
    } finally {
      setAtribuindoId(null);
    }
  }

  useEffect(() => {
    carregarDashboard();
    carregarUsuarios();
    carregarOportunidadesSemCorretor();
    carregarStatusWorkerDatasCaixa();
    const intervaloStatusDatas = window.setInterval(
      carregarStatusWorkerDatasCaixa,
      30000
    );
    return () => {
      window.clearInterval(intervaloStatusDatas);
      pararEnriquecimentoCaixa.current = true;
    };
  }, []);

  function voltar() {
    window.location.href = "/";
  }

  async function criarUsuario(e) {
    e.preventDefault();

    try {
      setCriando(true);

      const resposta = await fetch(`${API_URL}/usuarios`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          nome: novoNome,
          email: novoEmail,
          senha: novaSenha,
          tipo: novoTipo,
        }),
      });

      const corpo = await resposta.json();

      if (!resposta.ok) {
        throw new Error(corpo.detail || "Não foi possível criar o usuário.");
      }

      setUsuarios((lista) => [...lista, corpo]);
      setNovoNome("");
      setNovoEmail("");
      setNovaSenha("");
      setNovoTipo("cliente");
      setMostrarNovo(false);

      await carregarDashboard();
    } catch (error) {
      alert(error.message);
    } finally {
      setCriando(false);
    }
  }

  function iniciarEdicao(item) {
    setEditandoId(item.id);
    setEditNome(item.nome);
    setEditEmail(item.email);
    setEditSenha("");
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setEditNome("");
    setEditEmail("");
    setEditSenha("");
  }

  async function salvarEdicao(id) {
    try {
      setSalvando(true);

      const corpo = {
        nome: editNome,
        email: editEmail,
      };

      if (editSenha.trim()) {
        corpo.senha = editSenha;
      }

      const resposta = await fetch(`${API_URL}/admin/usuarios/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(corpo),
      });

      const resultado = await resposta.json();

      if (!resposta.ok) {
        throw new Error(
          resultado.detail || "Não foi possível atualizar o usuário."
        );
      }

      setUsuarios((lista) =>
        lista.map((item) => (item.id === id ? resultado : item))
      );

      cancelarEdicao();
    } catch (error) {
      alert(error.message);
    } finally {
      setSalvando(false);
    }
  }

  async function alternarAdmin(item) {
    try {
      const resposta = await fetch(`${API_URL}/admin/usuarios/${item.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          admin: !item.admin,
        }),
      });

      const resultado = await resposta.json();

      if (!resposta.ok) {
        throw new Error(
          resultado.detail || "Não foi possível alterar a permissão."
        );
      }

      setUsuarios((lista) =>
        lista.map((usuarioItem) =>
          usuarioItem.id === item.id ? resultado : usuarioItem
        )
      );
    } catch (error) {
      alert(error.message);
    }
  }

  async function excluirUsuario(item) {
    if (item.id === usuario?.id) {
      alert("Você não pode excluir o próprio usuário.");
      return;
    }

    const confirmar = window.confirm(
      `Excluir o usuário ${item.nome}?\n\nEssa ação não pode ser desfeita.`
    );

    if (!confirmar) {
      return;
    }

    try {
      const resposta = await fetch(`${API_URL}/admin/usuarios/${item.id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      const resultado = await resposta.json();

      if (!resposta.ok) {
        throw new Error(
          resultado.detail || "Não foi possível excluir o usuário."
        );
      }

      setUsuarios((lista) =>
        lista.filter((usuarioItem) => usuarioItem.id !== item.id)
      );

      await carregarDashboard();
    } catch (error) {
      alert(error.message);
    }
  }

  return (
    <div className="admin-page">
      <header className="admin-header">
        <div>
          <span className="admin-eyebrow">RADAR LEILÃO</span>
          <h1>Painel administrativo</h1>
          <p>
            Olá, <strong>{usuario?.nome || usuario?.sub}</strong>
          </p>
        </div>

        <div className="admin-header-actions">
          <span className="user-role-badge">Administrador</span>
          <button
            type="button"
            className="admin-back-button"
            onClick={voltar}
          >
            Voltar para os imóveis
          </button>
          <button
            type="button"
            className="header-logout admin-logout"
            onClick={onLogout}
          >
            Sair
          </button>
        </div>
      </header>

      <main className="admin-content">
        <div className="admin-dashboard-heading">
          <div>
            <span>INDICADORES DO SISTEMA</span>
            <h2>Resumo</h2>
          </div>
          <button
            type="button"
            className="admin-secondary-button"
            onClick={carregarDashboard}
            disabled={loadingDashboard}
          >
            {loadingDashboard ? "Atualizando..." : "Atualizar indicadores"}
          </button>
        </div>

        <section className="admin-date-enrichment">
          <div className="admin-date-enrichment-copy">
            <span>ATUALIZAÇÃO DA CAIXA</span>
            <h2>Datas dos leilões</h2>
            <p>
              O backend consulta em segundo plano, um imóvel por vez. O progresso
              fica salvo e a tela pode ser fechada; após um bloqueio, a busca
              retoma automaticamente com uma espera maior.
            </p>
            {statusWorkerDatasCaixa && (
              <p className="admin-date-enrichment-message" role="status">
                {statusWorkerDatasCaixa.status === "AGUARDANDO"
                  ? `Worker aguardando a CAIXA liberar o acesso${statusWorkerDatasCaixa.bloqueado_ate ? ` até ${new Date(statusWorkerDatasCaixa.bloqueado_ate).toLocaleString("pt-BR")}` : ""}.`
                  : statusWorkerDatasCaixa.status === "ATIVO"
                    ? "Worker automático ativo."
                    : statusWorkerDatasCaixa.status === "CONCLUIDO"
                      ? "Fila atual concluída."
                      : "Worker automático desativado."}
              </p>
            )}
            {enriquecimentoCaixa.mensagem && (
              <p className="admin-date-enrichment-message" role="status">
                {enriquecimentoCaixa.mensagem}
              </p>
            )}
            {(enriquecimentoCaixa.processados > 0 || enriquecimentoCaixa.cursor) && (
              <div className="admin-date-enrichment-progress">
                <span>Processados: {formatarNumero(enriquecimentoCaixa.processados)}</span>
                <span>Datas preenchidas: {formatarNumero(enriquecimentoCaixa.atualizados)}</span>
                <span>Sem novas datas: {formatarNumero(enriquecimentoCaixa.semDadosNovos)}</span>
                <span>Erros: {formatarNumero(enriquecimentoCaixa.erros)}</span>
              </div>
            )}
          </div>
        </section>

        {loadingDashboard && (
          <div className="admin-dashboard-message" role="status">
            <div className="admin-spinner" />
            <p>Carregando indicadores...</p>
          </div>
        )}

        {erroDashboard && (
          <div className="admin-dashboard-message is-error" role="alert">
            <div>
              <strong>Não foi possível carregar os indicadores</strong>
              <p>{erroDashboard}</p>
            </div>
            <button type="button" className="admin-secondary-button" onClick={carregarDashboard}>
              Tentar novamente
            </button>
          </div>
        )}

        {!loadingDashboard && !erroDashboard && dashboardIncompleto && (
          <div className="admin-dashboard-message is-incomplete" role="status">
            A API retornou dados incompletos. Campos ausentes são exibidos como zero.
          </div>
        )}

        {dashboard && (
          <div className="admin-dashboard-sections">
            <section className="admin-summary-section">
              <div className="admin-metric-heading">
                <span>RESUMO</span>
                <h2>Imóveis e usuários</h2>
              </div>
              <div className="admin-summary-groups">
                <div>
                  <h3>Imóveis</h3>
                  <div className="admin-metric-grid">
                    <Indicador rotulo="Total" valor={dashboard.imoveis.total} destaque />
                    <Indicador rotulo="Ativos" valor={dashboard.imoveis.ativos} />
                    <Indicador rotulo="Encerrados" valor={dashboard.imoveis.encerrados} />
                  </div>
                </div>
                <div>
                  <h3>Usuários</h3>
                  <div className="admin-metric-grid">
                    <Indicador rotulo="Total" valor={dashboard.usuarios.total} destaque />
                    <Indicador rotulo="Clientes" valor={dashboard.usuarios.clientes} />
                    <Indicador rotulo="Corretores" valor={dashboard.usuarios.corretores} />
                    <Indicador rotulo="Administradores" valor={dashboard.usuarios.administradores} />
                  </div>
                </div>
              </div>
            </section>

            <SecaoIndicadores titulo="Oportunidades" legenda="ACOMPANHAMENTO" itens={[
              ["Total", dashboard.oportunidades.total],
              ["Interesse", dashboard.oportunidades.interesse],
              ["Em contato", dashboard.oportunidades.em_contato],
              ["Negociando", dashboard.oportunidades.negociando],
              ["Concluídas", dashboard.oportunidades.concluida],
              ["Canceladas", dashboard.oportunidades.cancelada],
            ]} />

            <SecaoIndicadores titulo="Negociações" legenda="PROPOSTAS" itens={[
              ["Total", dashboard.negociacoes.total],
              ["Abertas", dashboard.negociacoes.abertas],
              ["Contrapropostas", dashboard.negociacoes.contrapropostas],
              ["Aceitas", dashboard.negociacoes.aceitas],
              ["Recusadas", dashboard.negociacoes.recusadas],
              ["Canceladas", dashboard.negociacoes.canceladas],
            ]} />

            <SecaoIndicadores titulo="Operações" legenda="PÓS-NEGOCIAÇÃO" itens={[
              ["Total", dashboard.operacoes.total],
              ["Em andamento", dashboard.operacoes.em_andamento],
              ["Concluídas", dashboard.operacoes.concluida],
              ["Canceladas", dashboard.operacoes.cancelada],
            ]} />

            <SecaoIndicadores titulo="Fotos" legenda="ACERVO DE IMAGENS" itens={[
              ["Imóveis com fotos", dashboard.fotos.imoveis_com_fotos],
              ["Total de imagens", dashboard.fotos.total_imagens],
            ]} />
          </div>
        )}

        <section className="admin-section admin-users-section">
              <div className="admin-section-heading">
                <div className="admin-section-title">
                  <span>ENTRADA DO FUNIL</span>
                  <h2>Oportunidades sem corretor</h2>
                </div>
                <button type="button" className="admin-secondary-button" onClick={carregarOportunidadesSemCorretor}>
                  Atualizar lista
                </button>
              </div>
              {erroAtribuicao && <div className="admin-dashboard-message is-error" role="alert">{erroAtribuicao}</div>}
              {oportunidadesSemCorretor.length === 0 ? (
                <p>Nenhuma oportunidade ativa aguarda atribuição.</p>
              ) : (
                <div className="admin-users-list">
                  {oportunidadesSemCorretor.map((oportunidade) => (
                    <article className="admin-user-row" key={oportunidade.id}>
                      <div className="admin-user-info">
                        <strong>Oportunidade #{oportunidade.id}</strong>
                        <span>{oportunidade.imovel_id ? `Imóvel #${oportunidade.imovel_id}` : `Anúncio #${oportunidade.anuncio_id}`} · Cliente #{oportunidade.cliente_id}</span>
                      </div>
                      <div className="admin-user-actions">
                        <select
                          aria-label={`Selecionar corretor para oportunidade ${oportunidade.id}`}
                          value={corretoresSelecionados[oportunidade.id] || ""}
                          onChange={(evento) => setCorretoresSelecionados((atuais) => ({ ...atuais, [oportunidade.id]: evento.target.value }))}
                        >
                          <option value="">Selecionar corretor</option>
                          {usuarios.filter((item) => item.tipo === "corretor").map((corretor) => (
                            <option key={corretor.id} value={corretor.id}>{corretor.nome} · {corretor.email}</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="admin-primary-button"
                          disabled={!corretoresSelecionados[oportunidade.id] || atribuindoId === oportunidade.id}
                          onClick={() => atribuirOportunidade(oportunidade.id)}
                        >
                          {atribuindoId === oportunidade.id ? "Atribuindo..." : "Atribuir"}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
        </section>

        <section className="admin-section admin-users-section">
              <div className="admin-section-heading">
                <div className="admin-section-title">
                  <span>CONTROLE DE ACESSO</span>
                  <h2>Usuários</h2>
                </div>

                <button
                  type="button"
                  className="admin-primary-button"
                  onClick={() => setMostrarNovo((valor) => !valor)}
                >
                  {mostrarNovo ? "Cancelar" : "+ Novo usuário"}
                </button>
              </div>

              {mostrarNovo && (
                <form className="admin-user-form" onSubmit={criarUsuario}>
                  <div className="admin-form-grid">
                    <label>
                      Nome
                      <input
                        value={novoNome}
                        onChange={(e) => setNovoNome(e.target.value)}
                        required
                      />
                    </label>

                    <label>
                      E-mail
                      <input
                        type="email"
                        value={novoEmail}
                        onChange={(e) => setNovoEmail(e.target.value)}
                        required
                      />
                    </label>

                    <label>
                      Senha
                      <input
                        type="password"
                        value={novaSenha}
                        onChange={(e) => setNovaSenha(e.target.value)}
                        minLength={6}
                        required
                      />
                    </label>

                    <label>
                      Tipo de usuário
                      <select
                        value={novoTipo}
                        onChange={(e) => setNovoTipo(e.target.value)}
                        required
                      >
                        <option value="cliente">Cliente</option>
                        <option value="corretor">Corretor</option>
                        <option value="admin">Administrador</option>
                      </select>
                    </label>
                  </div>

                  <button
                    type="submit"
                    className="admin-primary-button"
                    disabled={criando}
                  >
                    {criando ? "Criando..." : "Criar usuário"}
                  </button>
                </form>
              )}

              {carregandoUsuarios && (
                <div className="admin-users-state">
                  <div className="admin-spinner" />
                  <p>Carregando usuários...</p>
                </div>
              )}

              {!carregandoUsuarios && erroUsuarios && (
                <div className="admin-users-state admin-state-error">
                  <p>{erroUsuarios}</p>
                  <button type="button" onClick={carregarUsuarios}>
                    Tentar novamente
                  </button>
                </div>
              )}

              {!carregandoUsuarios && !erroUsuarios && (
                <div className="admin-users-list">
                  {usuarios.map((item) => (
                    <article className="admin-user-row" key={item.id}>
                      {editandoId === item.id ? (
                        <div className="admin-user-edit">
                          <div className="admin-form-grid">
                            <label>
                              Nome
                              <input
                                value={editNome}
                                onChange={(e) => setEditNome(e.target.value)}
                              />
                            </label>

                            <label>
                              E-mail
                              <input
                                type="email"
                                value={editEmail}
                                onChange={(e) => setEditEmail(e.target.value)}
                              />
                            </label>

                            <label>
                              Nova senha
                              <input
                                type="password"
                                placeholder="Deixe vazio para manter"
                                value={editSenha}
                                onChange={(e) => setEditSenha(e.target.value)}
                              />
                            </label>
                          </div>

                          <div className="admin-user-actions">
                            <button
                              type="button"
                              className="admin-primary-button"
                              disabled={salvando}
                              onClick={() => salvarEdicao(item.id)}
                            >
                              {salvando ? "Salvando..." : "Salvar"}
                            </button>

                            <button
                              type="button"
                              className="admin-secondary-button"
                              onClick={cancelarEdicao}
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="admin-user-info">
                            <strong>{item.nome}</strong>
                            <span>{item.email}</span>
                          </div>

                          <div className="admin-user-role">
                            <span className="admin-badge">
                              {({
                                cliente: "Cliente",
                                corretor: "Corretor",
                                admin: "Administrador",
                              })[item.tipo] || item.tipo || "Tipo não informado"}
                            </span>
                            <span
                              className={
                                item.admin
                                  ? "admin-badge admin-badge-admin"
                                  : "admin-badge"
                              }
                            >
                              {item.admin ? "Admin ativo" : "Sem admin"}
                            </span>
                          </div>

                          <div className="admin-user-actions">
                            <button
                              type="button"
                              className="admin-secondary-button"
                              onClick={() => iniciarEdicao(item)}
                            >
                              Editar
                            </button>

                            <button
                              type="button"
                              className="admin-secondary-button"
                              onClick={() => alternarAdmin(item)}
                              disabled={item.id === usuario?.id}
                            >
                              {item.admin
                                ? "Remover admin"
                                : "Tornar admin"}
                            </button>

                            <button
                              type="button"
                              className="admin-danger-button"
                              onClick={() => excluirUsuario(item)}
                              disabled={item.id === usuario?.id}
                            >
                              Excluir
                            </button>
                          </div>
                        </>
                      )}
                    </article>
                  ))}
                </div>
              )}
        </section>
      </main>
    </div>
  );
}

export default Admin;
