import { useCallback, useEffect, useRef, useState } from "react";
import Login from "./Login";
import Admin from "./Admin";
import Oportunidade from "./Oportunidade";
import MinhasOportunidades from "./MinhasOportunidades";
import Corretor from "./Corretor";
import StatusCaixa from "./StatusCaixa";
import Alertas from "./Alertas";
import Consultoria from "./Consultoria";
import {
  Search,
  MapPin,
  Home,
  Tag,
  ExternalLink,
  SlidersHorizontal,
  X,
  ArrowDownUp,
  Building2,
  Gavel,
  Image as ImageIcon,
  Heart,
  Info,
  CircleCheck,
  AlertTriangle,
  CircleX,
  Ruler,
  BedDouble,
  Bath,
  Car,
  LogOut,
  Columns3,
} from "lucide-react";

import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function papelDoUsuario(usuario) {
  if (usuario?.admin === true || usuario?.tipo === "admin") {
    return "admin";
  }

  return ["cliente", "corretor"].includes(usuario?.tipo)
    ? usuario.tipo
    : null;
}

const ROTULOS_PAPEL = {
  cliente: "Cliente",
  corretor: "Corretor",
  admin: "Administrador",
};

function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem("radar-leilao-token")
  );

  const [usuario, setUsuario] = useState(null);
  const [verificandoAutenticacao, setVerificandoAutenticacao] = useState(true);
  const papel = papelDoUsuario(usuario);
  const ehAdministrador = papel === "admin";

  const [imoveis, setImoveis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const requisicaoImoveisAtual = useRef(0);

  const [pagina, setPagina] = useState(1);
  const [total, setTotal] = useState(0);
  const [limite] = useState(20);
  const [paginas, setPaginas] = useState(1);
  const [favoritos, setFavoritos] = useState(() => {
    try {
      const salvos = localStorage.getItem("radar-leilao-favoritos");

      if (!salvos) return [];
      
      const dados = JSON.parse(salvos);

      return [...new Set(
        dados
          .map((item) => {
            if (typeof item === "object" && item !== null) {
              return item.id;
            }

            return item;
          })
          .filter((id) => id !== null && id !== undefined)
      )];
    } catch {
      return [];
    }
  });


  const [mostrarFavoritos, setMostrarFavoritos] = useState(false);

  const [busca, setBusca] = useState("");
  const [estado, setEstado] = useState("");
  const [tipo, setTipo] = useState("");
  const [statusLeilao, setStatusLeilao] = useState("ativos");
  const [descontoMinimo, setDescontoMinimo] = useState("");
  const [valorMaximo, setValorMaximo] = useState("");

  const [areaMin, setAreaMin] = useState("");
  const [areaMax, setAreaMax] = useState("");
  const [quartos, setQuartos] = useState("");
  const [banheiros, setBanheiros] = useState("");
  const [vagas, setVagas] = useState("");

  const [ordenacao, setOrdenacao] = useState("desconto");

  const [filtrosAbertos, setFiltrosAbertos] = useState(false);
  const [galeriaAberta, setGaleriaAberta] = useState(null);
  const [fotoAtiva, setFotoAtiva] = useState(0);
  const [fotoDetalhesAtiva, setFotoDetalhesAtiva] = useState(0);
  const [imovelDetalhes, setImovelDetalhes] = useState(null);
  const [oportunidadeSelecionada, setOportunidadeSelecionada] = useState(null);
  const [custosArremate, setCustosArremate] = useState({});
  const [cenariosSelecionados, setCenariosSelecionados] = useState({});
  const [imoveisComparacao, setImoveisComparacao] = useState([]);
  const [pesquisaVersion, setPesquisaVersion] = useState(0);



  useEffect(() => {
    async function verificarUsuario() {
      if (!token) {
        setUsuario(null);
        setVerificandoAutenticacao(false);
        return;
      }

      try {
        const resposta = await fetch(`${API_URL}/usuarios/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!resposta.ok) {
          throw new Error("Sessão inválida.");
        }

        const dados = await resposta.json();

        setUsuario(dados);
      } catch (erro) {
        console.error("Erro ao verificar autenticação:", erro);

        localStorage.removeItem("radar-leilao-token");
        setToken(null);
        setUsuario(null);
      } finally {
        setVerificandoAutenticacao(false);
      }
    }

    verificarUsuario();
  }, [token]);

  function sair() {
    localStorage.removeItem("radar-leilao-token");
    setUsuario(null);
    setToken(null);
    setVerificandoAutenticacao(false);

    if (window.location.pathname === "/admin") {
      window.history.replaceState({}, "", "/");
    }
  }

  useEffect(() => {
    localStorage.setItem(
      "radar-leilao-favoritos",
      JSON.stringify(favoritos)
    );
  }, [favoritos]);
 
  // =========================================================
  // FORMATAÇÃO
  // =========================================================

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

  function formatarData(data) {
    if (!data) return "Não informada";

    const valor = new Date(`${data}T00:00:00`);

    return Number.isNaN(valor.getTime())
      ? "Não informada"
      : valor.toLocaleDateString("pt-BR");
  }

  function dataCivil(data) {
    if (!data) return null;
    const correspondencia = String(data).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (correspondencia) {
      return new Date(
        Number(correspondencia[1]),
        Number(correspondencia[2]) - 1,
        Number(correspondencia[3])
      );
    }
    const valor = new Date(data);
    return Number.isNaN(valor.getTime()) ? null : valor;
  }

  function analiseFinanceira(imovel, custosPersonalizados = {}) {
    const avaliacao = Number(imovel?.valor_avaliacao);
    const leilao = Number(imovel?.valor_leilao);
    const area = Number(imovel?.area_util ?? imovel?.area);

    const economia =
      Number.isFinite(avaliacao) && Number.isFinite(leilao)
        ? avaliacao - leilao
        : null;

    const valorM2Avaliacao =
      Number.isFinite(avaliacao) && Number.isFinite(area) && area > 0
        ? avaliacao / area
        : null;

    const valorM2Leilao =
      Number.isFinite(leilao) && Number.isFinite(area) && area > 0
        ? leilao / area
        : null;

    const custoInformado = (campo, valorDoImovel, valorPadrao) => {
      if (custosPersonalizados[campo] !== undefined) {
        return Math.max(0, Number(custosPersonalizados[campo]) || 0);
      }

      const valor = Number(valorDoImovel);
      return Number.isFinite(valor) && valor >= 0 ? valor : valorPadrao;
    };

    const comissao = custoInformado(
      "comissao",
      imovel?.comissao_leiloeiro,
      Number.isFinite(leilao) ? leilao * 0.05 : 0
    );
    const itbi = custoInformado(
      "itbi",
      imovel?.itbi,
      Number.isFinite(leilao) ? leilao * 0.03 : 0
    );
    const registro = custoInformado(
      "registro",
      imovel?.registro,
      Number.isFinite(leilao) ? leilao * 0.01 : 0
    );
    const outrosCustos = custoInformado(
      "outrosCustos",
      imovel?.outros_custos,
      0
    );
    const custoVenda = custoInformado(
      "custoVenda",
      imovel?.custo_venda,
      Number.isFinite(avaliacao) ? avaliacao * 0.06 : 0
    );
    const custoReforma = custoInformado(
      "custoReforma",
      imovel?.custo_reforma,
      0
    );

    const custoTotal = Number.isFinite(leilao)
      ? leilao + comissao + itbi + registro + outrosCustos
      : null;

    const custoInvestimento = Number.isFinite(custoTotal)
      ? custoTotal + custoReforma
      : null;

    const margemPotencial =
      Number.isFinite(avaliacao) && Number.isFinite(custoTotal)
        ? avaliacao - custoTotal
        : null;

    const valorRevenda = custoInformado(
      "valorRevenda",
      imovel?.valor_revenda,
      Number.isFinite(avaliacao) ? avaliacao : 0
    );

    const receitaLiquidaRevenda = Number.isFinite(valorRevenda)
      ? Math.max(0, valorRevenda - custoVenda)
      : null;

    const lucroRealEstimado =
      receitaLiquidaRevenda !== null && custoInvestimento !== null
        ? receitaLiquidaRevenda - custoInvestimento
        : null;

    const retornoSobreInvestimento =
      lucroRealEstimado !== null && custoInvestimento > 0
        ? (lucroRealEstimado / custoInvestimento) * 100
        : null;

    const margemSeguranca =
      Number.isFinite(valorRevenda) &&
      Number.isFinite(custoInvestimento) &&
      valorRevenda > 0
        ? ((valorRevenda - custoInvestimento) / valorRevenda) * 100
        : null;

    return {
      avaliacao,
      leilao,
      economia,
      valorM2Avaliacao,
      valorM2Leilao,
      comissao,
      itbi,
      registro,
      outrosCustos,
      custoVenda,
      custoReforma,
      custoTotal,
      custoInvestimento,
      margemPotencial,
      valorRevenda,
      receitaLiquidaRevenda,
      lucroRealEstimado,
      retornoSobreInvestimento,
      margemSeguranca,
    };
  }

  function analiseDoCenario(imovel, cenario) {
    const base = analiseFinanceira(imovel, {});
    const custosNaoInformados = cenario.custos_nao_informados || [];
    const temCustosAusentes = custosNaoInformados.length > 0;
    const lucro = Number(cenario.lucro_estimado);
    const roi = cenario.roi == null ? null : Number(cenario.roi);
    const margem = cenario.margem_revenda == null ? null : Number(cenario.margem_revenda);
    return {
      ...base,
      leilao: Number(cenario.preco_aquisicao),
      comissao: 0,
      itbi: Number(cenario.impostos_taxas) || 0,
      registro: Number(cenario.custos_juridicos) || 0,
      outrosCustos: Number(cenario.outras_despesas) || 0,
      custoVenda: 0,
      custoReforma: Number(cenario.reformas) || 0,
      custoTotal: Number(cenario.custo_total),
      custoInvestimento: Number(cenario.custo_total),
      valorRevenda: Number(cenario.valor_revenda),
      receitaLiquidaRevenda: Number(cenario.valor_revenda),
      lucroRealEstimado: Number.isFinite(lucro) ? lucro : null,
      retornoSobreInvestimento: !temCustosAusentes && Number.isFinite(roi) ? roi : null,
      margemSeguranca: !temCustosAusentes && Number.isFinite(margem) ? margem : null,
      custosNaoInformados,
      cenario,
    };
  }

  function calcularDesconto(imovel) {
    const avaliacao = Number(imovel.valor_avaliacao);
    const leilao = Number(imovel.valor_leilao);

    if (
      !Number.isFinite(avaliacao) ||
      !Number.isFinite(leilao) ||
      avaliacao <= 0 ||
      leilao <= 0
    ) {
      return null;
    }

    const percentual =
      ((avaliacao - leilao) / avaliacao) * 100;

    if (percentual <= 0 || percentual > 100) {
      return null;
    }

    return percentual;
  }

  function calcularEconomia(imovel) {
    const avaliacao = Number(imovel.valor_avaliacao || 0);
    const leilao = Number(imovel.valor_leilao || 0);

    if (!avaliacao || !leilao) {
      return 0;
    }

    return Math.max(0, avaliacao - leilao);
  }

 function calcularScoreOportunidade(imovel, custosPersonalizados = {}, cenarioSelecionado = null) {
  const desconto = calcularDesconto(imovel);
  const economia = calcularEconomia(imovel);

  const analise = cenarioSelecionado
    ? analiseDoCenario(imovel, cenarioSelecionado)
    : analiseFinanceira(imovel, custosPersonalizados);

  const area = Number(
    imovel?.area_util ?? imovel?.area ?? 0
  );

  // =====================================================
  // 1. DESCONTO — 30 PONTOS
  // =====================================================

  const pontosDesconto =
    desconto !== null
      ? Math.min(30, Math.max(0, Math.round(desconto)))
      : 0;

  // =====================================================
  // 2. ECONOMIA TOTAL — 15 PONTOS
  // =====================================================

  let pontosEconomia = 0;

  if (economia > 0) {
    if (economia >= 100000) {
      pontosEconomia = 15;
    } else if (economia >= 50000) {
      pontosEconomia = 12;
    } else if (economia >= 30000) {
      pontosEconomia = 9;
    } else if (economia >= 15000) {
      pontosEconomia = 6;
    } else if (economia >= 5000) {
      pontosEconomia = 3;
    }
  }

  // =====================================================
  // 3. ECONOMIA POR m² — 10 PONTOS
  // =====================================================

  const economiaPorM2 =
    Number.isFinite(economia) &&
    Number.isFinite(area) &&
    area > 0
      ? economia / area
      : null;

  let pontosEconomiaM2 = 0;

  if (economiaPorM2 !== null && economiaPorM2 > 0) {
    if (economiaPorM2 >= 2000) {
      pontosEconomiaM2 = 10;
    } else if (economiaPorM2 >= 1500) {
      pontosEconomiaM2 = 8;
    } else if (economiaPorM2 >= 1000) {
      pontosEconomiaM2 = 6;
    } else if (economiaPorM2 >= 500) {
      pontosEconomiaM2 = 4;
    } else if (economiaPorM2 >= 250) {
      pontosEconomiaM2 = 2;
    }
  }

  // =====================================================
  // 4. DADOS ESSENCIAIS — 15 PONTOS
  // =====================================================

  const temDesconto = desconto !== null;

  const temArea = area > 0;

  const temLocalizacao = Boolean(
    imovel?.cidade && imovel?.estado
  );

  const temValores =
    Number(imovel?.valor_avaliacao) > 0 &&
    Number(imovel?.valor_leilao) > 0;

  const dadosCompletos = [
    temDesconto,
    temArea,
    temLocalizacao,
    temValores,
  ];

  const pontosDados =
    (temDesconto ? 4 : 0) +
    (temArea ? 4 : 0) +
    (temLocalizacao ? 4 : 0) +
    (temValores ? 3 : 0);

  // =====================================================
  // 5. DATA DO LEILÃO — 10 PONTOS
  // =====================================================

  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  const datasLeilao = [
    imovel?.data_primeiro_leilao,
    imovel?.data_segundo_leilao,
    imovel?.data_licitacao_aberta,
  ]
    .filter(Boolean)
    .map(dataCivil)
    .filter(Boolean)
    .sort((a, b) => a - b);

  const datasFuturas = datasLeilao.filter(
    (data) => data >= hoje
  );

  const proximaDataLeilao =
    datasFuturas.length > 0
      ? datasFuturas[0]
      : null;

  const leilaoJaRealizado =
    datasLeilao.length > 0 &&
    !proximaDataLeilao;

  let pontosData = 0;
  let diasAteLeilao = null;

  if (proximaDataLeilao) {
    diasAteLeilao = Math.ceil(
      (proximaDataLeilao - hoje) /
        (1000 * 60 * 60 * 24)
    );

    if (diasAteLeilao <= 30) {
      pontosData = 10;
    } else if (diasAteLeilao <= 90) {
      pontosData = 8;
    } else if (diasAteLeilao <= 180) {
      pontosData = 5;
    } else {
      pontosData = 2;
    }
  }

  // =====================================================
  // 6. RESULTADO FINANCEIRO — 20 PONTOS
  // =====================================================

  let pontosROI = 0;
  let pontosMargem = 0;

  const roi = analise?.retornoSobreInvestimento;
  const margem = analise?.margemSeguranca;

  if (Number.isFinite(roi)) {
    if (roi > 30) {
      pontosROI = 10;
    } else if (roi > 20) {
      pontosROI = 8;
    } else if (roi > 10) {
      pontosROI = 5;
    } else if (roi > 0) {
      pontosROI = 2;
    }
  }

  if (Number.isFinite(margem)) {
    if (margem > 30) {
      pontosMargem = 10;
    } else if (margem > 20) {
      pontosMargem = 8;
    } else if (margem > 10) {
      pontosMargem = 5;
    } else if (margem > 0) {
      pontosMargem = 2;
    }
  }

  const pontosFinanceiros =
    pontosROI + pontosMargem;

  // =====================================================
  // SCORE FINAL — 100 PONTOS
  // =====================================================

  const valor = Math.min(
    100,
    pontosDesconto +
      pontosEconomia +
      pontosEconomiaM2 +
      pontosDados +
      pontosData +
      pontosFinanceiros
  );

  // =====================================================
  // CLASSIFICAÇÃO
  // =====================================================

  let classe;
  let texto;

  if (valor >= 80) {
    classe = "excelente";
    texto = "Excelente oportunidade";
  } else if (valor >= 65) {
    classe = "boa";
    texto = "Boa oportunidade";
  } else if (valor >= 45) {
    classe = "media";
    texto = "Oportunidade a avaliar";
  } else {
    classe = "baixa";
    texto = "Baixo potencial";
  }

  return {
    valor,
    classe,
    texto,

    desconto,
    economia,
    economiaPorM2,

    pontosDesconto,
    pontosEconomia,
    pontosEconomiaM2,
    pontosDados,
    pontosData,

    pontosROI,
    pontosMargem,
    pontosFinanceiros,

    dadosCompletos,
    diasAteLeilao,
    leilaoJaRealizado,
    proximaDataLeilao,

    roi,
    margem,
  };
}

  function decisaoDaOportunidade(imovel, custosPersonalizados = {}, cenarioSelecionado = null) {
   const score = calcularScoreOportunidade(
    imovel,
    custosPersonalizados,
    cenarioSelecionado
  );
    const desconto = calcularDesconto(imovel);

    const ocupado = imovel?.ocupado;

    // =====================================================
    // IMÓVEL CONFIRMADAMENTE OCUPADO
    // =====================================================

    if (ocupado === true) {
      return {
        classe: "evitar",
        titulo: "Risco elevado",
        descricao:
          "Imóvel ocupado. Avalie cuidadosamente os custos, prazo e riscos de desocupação antes de arrematar.",
        Icone: AlertTriangle
      };
    }

    // LEILÕES JÁ ENCERRADOS
    const alertas = alertasDoImovel(imovel);

    const leiloesEncerrados = alertas.some(
      (alerta) => alerta.tipo === "danger"
    );

    if (leiloesEncerrados) {
      return {
        classe: "atencao",
        titulo: "Leilão sem oportunidade de compra no momento",
        descricao:
          "O imóvel apresenta potencial financeiro, mas todos os leilões identificados já foram realizados. É necessário verificar se haverá nova oferta ou atualização do edital.",
        Icone: AlertTriangle
      };
    }

    // =====================================================
    // DADOS INSUFICIENTES
    // =====================================================

    if (
      score.valor < 45 ||
      desconto === null
    ) {
      return {
        classe: "evitar",
        titulo: "Dados insuficientes",
        descricao:
          "Não há informações suficientes para considerar este imóvel uma boa oportunidade.",
        Icone: CircleX
      };
    }

    // LEILÃO ACONTECE HOJE
    const leilaoHoje = alertas.some(
      (alerta) => alerta.texto === "Leilão acontece hoje"
    );

    if (leilaoHoje) {
      return {
        classe: "atencao",
        titulo: "Ação imediata necessária",
        descricao:
          "O leilão acontece hoje. Confira imediatamente o edital, horário, condições de pagamento e documentação antes de participar.",
        Icone: AlertTriangle
      };
    }

    if (cenarioSelecionado?.custos_nao_informados?.length) {
      return {
        classe: "atencao",
        titulo: "Custos do cenário a confirmar",
        descricao: `O cenário “${cenarioSelecionado.nome}” tem custos não informados (${cenarioSelecionado.custos_nao_informados.join(", ")}). Confirme esses valores antes de considerar o resultado financeiro.`,
        Icone: AlertTriangle,
      };
    }

    // LEILÃO PRÓXIMO
    const leilaoProximo = alertas.find(
      (alerta) =>
        alerta.tipo === "warning" &&
        alerta.texto.startsWith("Próximo leilão em")
    );

    if (leilaoProximo && score.valor >= 80) {
      return {
        classe: "vale",
        titulo: "Vale a pena analisar",
        descricao:
          `${leilaoProximo.texto}. Excelente potencial pelos dados disponíveis. Verifique o edital, matrícula e custos antes de arrematar.`,
        Icone: CircleCheck
      };
    }

    if (leilaoProximo && score.valor >= 65) {
      return {
        classe: "boa",
        titulo: "Boa oportunidade para analisar",
        descricao:
          `${leilaoProximo.texto}. O imóvel apresenta bom potencial, mas é importante verificar o edital, matrícula e custos antes de arrematar.`,
        Icone: AlertTriangle
      };
    }


    // =====================================================
    // EXCELENTE
    // =====================================================

if (score.valor >= 80) {
  return {
    classe: "excelente",
    titulo: "Excelente oportunidade",
    descricao:
      "Excelente potencial pelos dados disponíveis, mas ainda é necessário confirmar as informações do imóvel, edital e custos antes de arrematar.",
    Icone: CircleCheck
  };
}


// =====================================================
// BOA OPORTUNIDADE
// =====================================================

if (score.valor >= 65) {
  return {
    classe: "boa",
    titulo: "Boa oportunidade",
    descricao:
      "Bom potencial pelos dados disponíveis, mas é necessário confirmar as informações do imóvel, edital e custos antes de arrematar.",
    Icone: AlertTriangle
  };
}


    // OPORTUNIDADE MÉDIA
    // =====================================================

    return {
      classe: "atencao",
      titulo: "Atenção",
      descricao:
        "O imóvel apresenta potencial, mas é necessário analisar os detalhes antes de arrematar.",
      Icone: AlertTriangle
    };
  }

  function prioridadeDoImovel(imovel) {
    const score = calcularScoreOportunidade(imovel);
    const hoje = new Date();
    hoje.setHours(0, 0, 0, 0);

    const datas = [
      imovel?.data_primeiro_leilao,
      imovel?.data_segundo_leilao,
      imovel?.data_licitacao_aberta,
    ]
      .map(dataCivil)
      .filter(Boolean)
      .sort((a, b) => a - b);

    const dataFutura = datas.find((data) => data >= hoje);

    // SEM LEILÃO FUTURO
    if (!dataFutura) {
      return {
        nivel: "fora",
        label: "LEILÕES ENCERRADOS",
        classe: "prioridade-fora",
      };
    }

    const dias = Math.ceil(
      (dataFutura.getTime() - hoje.getTime()) /
        (1000 * 60 * 60 * 24)
    );

    // AGIR AGORA
    if (dias === 0 && score.valor >= 80) {
      return {
        nivel: "p1",
        label: "AGIR AGORA",
        classe: "prioridade-p1",
      };
    }

    // ALTA PRIORIDADE
    if (dias <= 7 && score.valor >= 80) {
      return {
        nivel: "p2",
        label: "ALTA PRIORIDADE",
        classe: "prioridade-p2",
      };
    }

    // ANALISAR
    if (dias <= 30 && score.valor >= 65) {
      return {
        nivel: "p3",
        label: "ANALISAR",
        classe: "prioridade-p3",
      };
    }

    // MONITORAR
    return {
      nivel: "p4",
      label: "MONITORAR",
      classe: "prioridade-p4",
    };
  }

  function alertasDoImovel(imovel) {
  const alertas = [];

  const fotos = Array.isArray(imovel?.imagens)
    ? imovel.imagens.filter(Boolean)
    : imovel?.imagem
      ? [imovel.imagem]
      : [];

  // FOTOS
  if (fotos.length === 0) {
    alertas.push({
      tipo: "info",
      texto: "Sem fotos disponíveis",
    });
  }

  // DATAS DOS LEILÕES
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  const datas = [
    imovel?.data_primeiro_leilao,
    imovel?.data_segundo_leilao,
    imovel?.data_licitacao_aberta,
  ]
    .map(dataCivil)
    .filter(Boolean)
    .sort((a, b) => a - b);

  const dataFutura = datas.find((data) => data >= hoje);

  if (dataFutura) {
    const dias = Math.ceil(
      (dataFutura.getTime() - hoje.getTime()) /
        (1000 * 60 * 60 * 24)
    );

    if (dias === 0) {
      alertas.push({
        tipo: "danger",
        texto: "Leilão acontece hoje",
      });
    } else if (dias <= 30) {
      alertas.push({
        tipo: "warning",
        texto: `Próximo leilão em ${dias} dias`,
      });
    } else if (dias <= 90) {
      alertas.push({
        tipo: "info",
        texto: `Próximo leilão em ${dias} dias`,
      });
    }
  } else if (datas.length > 0) {
    alertas.push({
      tipo: "danger",
      texto: "Todos os leilões já realizados",
    });
  }

  // ÁREA
  if (!(Number(imovel?.area) > 0)) {
    alertas.push({
      tipo: "warning",
      texto: "Área não informada",
    });
  }

  // VALORES
  if (
    !(Number(imovel?.valor_avaliacao) > 0) ||
    !(Number(imovel?.valor_leilao) > 0)
  ) {
    alertas.push({
      tipo: "warning",
      texto: "Valores do imóvel incompletos",
    });
  }

  // LOCALIZAÇÃO
  if (!imovel?.cidade || !imovel?.estado) {
    alertas.push({
      tipo: "warning",
      texto: "Localização incompleta",
    });
  }

  return alertas;
}

function detalhesDoScore(imovel, custosPersonalizados = {}, cenarioSelecionado = null) {
  const score = calcularScoreOportunidade(
  imovel,
  custosPersonalizados,
  cenarioSelecionado
);

const analise = cenarioSelecionado
  ? analiseDoCenario(imovel, cenarioSelecionado)
  : analiseFinanceira(imovel, custosPersonalizados);

  const financiamento = imovel?.aceita_financiamento;

  return {
    ...score,
    analise,
    condicoesCompra: [
      imovel?.ocupado !== undefined &&
        imovel?.ocupado !== null && {
          nome: "Ocupação",
          valor: imovel.ocupado ? "Ocupado" : "Desocupado",
        },

      imovel?.aceita_fgts !== undefined &&
        imovel?.aceita_fgts !== null && {
          nome: "FGTS",
          valor: imovel.aceita_fgts ? "Aceita" : "Não aceita",
        },

      financiamento !== undefined &&
        financiamento !== null && {
          nome: "Financiamento",
          valor: financiamento ? "Aceita" : "Não aceita",
        },
    ].filter(Boolean),
  };
}


  // =========================================================
  // FOTOS
  // =========================================================

  function fotosDoImovel(imovel) {
    if (!imovel) return [];

    const fontes = [];

    // A galeria persistida normalmente chega em "imagens".
    if (Array.isArray(imovel.imagens)) {
      fontes.push(...imovel.imagens.flat(Infinity));
    }

    // Alguns endpoints expõem a mesma galeria como "fotos".
    if (Array.isArray(imovel.fotos)) {
      fontes.push(...imovel.fotos.flat(Infinity));
    }

    if (Array.isArray(imovel.imagem)) {
      fontes.push(...imovel.imagem.flat(Infinity));
    } else if (typeof imovel.imagem === "string") {
      fontes.push(imovel.imagem);
    }

    return [...new Set(
      fontes
        .filter((foto) => typeof foto === "string")
        .map((foto) => foto.trim())
        .filter((foto) => /^https?:\/\//i.test(foto))
    )];
  }

  function abrirGaleria(imovel) {
    const fotos = fotosDoImovel(imovel);

    if (fotos.length === 0) {
      return;
    }

    setGaleriaAberta(imovel);
    setFotoAtiva(0);
  }

  function fotoAnterior() {
    if (!galeriaAberta) return;

    const fotos = fotosDoImovel(galeriaAberta);

    if (fotos.length <= 1) return;

    setFotoAtiva((atual) =>
      atual === 0 ? fotos.length - 1 : atual - 1
    );
  }

  function proximaFoto() {
    if (!galeriaAberta) return;

    const fotos = fotosDoImovel(galeriaAberta);

    if (fotos.length <= 1) return;

    setFotoAtiva((atual) =>
      atual === fotos.length - 1 ? 0 : atual + 1
    );
  }

  // =========================================================
  // PAGINAÇÃO
  // =========================================================

  function mudarPagina(novaPagina) {
    if (novaPagina < 1 || novaPagina > paginas) {
      return;
    }

    setPagina(novaPagina);

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  function paginasVisiveis() {
    const lista = [];

    if (paginas <= 7) {
      for (let i = 1; i <= paginas; i += 1) {
        lista.push(i);
      }

      return lista;
    }

    lista.push(1);

    if (pagina > 4) {
      lista.push("...");
    }

    const inicio = Math.max(2, pagina - 1);
    const fim = Math.min(paginas - 1, pagina + 1);

    for (let i = inicio; i <= fim; i += 1) {
      lista.push(i);
    }

    if (pagina < paginas - 3) {
      lista.push("...");
    }

    lista.push(paginas);

    return lista;
  }

  // =========================================================
  // API
  // =========================================================

  async function carregarImoveis() {
    const idRequisicao = ++requisicaoImoveisAtual.current;

    try {
      setLoading(true);
      setErro("");

      const params = new URLSearchParams();

      params.append("pagina", String(pagina));
      params.append("tamanho_pagina", String(limite));

      params.append(
        "modalidade",
        "Leilão SFI - Edital Único"
      );

      if (busca.trim()) {
        params.append("cidade", busca.trim());
      }

      if (estado) {
        params.append("estado", estado);
      }

      if (tipo) {
        params.append("tipo", tipo);
      }

      if (descontoMinimo !== "") {
        params.append(
          "desconto_minimo",
          descontoMinimo
        );
      }

      if (valorMaximo !== "") {
        params.append(
          "valor_maximo",
          valorMaximo
        );
      }

      if (areaMin !== "") {
        params.append("area_min", areaMin);
      }

      if (areaMax !== "") {
        params.append("area_max", areaMax);
      }

      if (quartos !== "") {
        params.append("quartos", quartos);
      }

      if (banheiros !== "") {
        params.append("banheiros", banheiros);
      }

      if (vagas !== "") {
        params.append("vagas", vagas);
      }

      params.append("status_leilao", statusLeilao);

      if (ordenacao === "score") {
        params.append("ordenar", "score");
        params.append("direcao", "desc");
      }

      if (ordenacao === "desconto") {
        params.append("ordenar", "desconto");
        params.append("direcao", "desc");
      }

      if (ordenacao === "menor-preco") {
        params.append("ordenar", "preco");
        params.append("direcao", "asc");
      }

      if (ordenacao === "economia-m2") {
        params.append("ordenar", "economia_m2");
        params.append("direcao", "desc");
      }

      if (ordenacao === "maior-area") {
        params.append("ordenar", "area");
        params.append("direcao", "desc");
      }

      if (ordenacao === "mais-recentes") {
        params.append("ordenar", "data");
        params.append("direcao", "asc");
      }

      const url =
        `${API_URL}/imoveis/?${params.toString()}`;

      const resposta = await fetch(url);
      const corpoResposta = await resposta.text();
      let dados;

      try {
        dados = JSON.parse(corpoResposta);
      } catch {
        throw new Error(
          `A API devolveu uma resposta que não é JSON (HTTP ${resposta.status}). ` +
            corpoResposta.slice(0, 300)
        );
      }

      if (!resposta.ok) {
        throw new Error(
          dados.detail || `Erro HTTP ${resposta.status}`
        );
      }

      const listaImoveis = Array.isArray(dados.items)
        ? dados.items
        : Array.isArray(dados.itens)
          ? dados.itens
          : null;

      if (!listaImoveis || !Number.isFinite(Number(dados.total))) {
        throw new Error(
          "Formato inesperado na resposta da API de imóveis: esperados items/itens e total."
        );
      }

      if (idRequisicao !== requisicaoImoveisAtual.current) return;

      setImoveis(listaImoveis);

      setTotal(
        Number(dados.total || 0)
      );

      setPaginas(
        Math.max(
          1,
      Number(dados.paginas_totais ?? dados.paginas ?? 1)
        )
      );
    } catch (error) {
      if (idRequisicao !== requisicaoImoveisAtual.current) return;

      console.error(
        "ERRO AO CARREGAR IMÓVEIS:",
        error
      );

      setErro(
        `Não foi possível carregar os imóveis: ${error.message || String(error)}`
      );
    } finally {
      if (idRequisicao === requisicaoImoveisAtual.current) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    carregarImoveis();
  }, [pagina, pesquisaVersion, ordenacao, statusLeilao]);

  // =========================================================
  // PESQUISA
  // =========================================================

  function pesquisar(event) {
    event?.preventDefault();

    if (pagina !== 1) {
      setPagina(1);
    }

    setPesquisaVersion(
      (valor) => valor + 1
    );
  }

  function quantidadeFiltrosAtivos() {
  return [
    busca,
    estado,
    tipo,
    descontoMinimo,
    valorMaximo,
    areaMin,
    areaMax,
    quartos,
    banheiros,
    vagas
  ].filter(
    (valor) => valor !== "" && valor !== null && valor !== undefined
  ).length;
}

  function limparFiltros() {
    setBusca("");
    setEstado("");
    setTipo("");
    setDescontoMinimo("");
    setValorMaximo("");

    setAreaMin("");
    setAreaMax("");
    setQuartos("");
    setBanheiros("");
    setVagas("");

    setStatusLeilao("ativos");
    setPagina(1);

    setPesquisaVersion(
      (valor) => valor + 1
    );
  }

  // =========================================================
  // LISTA EXIBIDA
  // Mantém a lista normal e filtra apenas quando Favoritos estiver ativo.
  // =========================================================

  const listaRenderizadaRadar = mostrarFavoritos
    ? imoveis.filter((imovel) =>
        favoritos.some((id) => String(id) === String(imovel.id))
      )
    : imoveis;

  function alternarComparacao(imovel) {
    setImoveisComparacao((atuais) => {
      const id = String(imovel.id);
      return atuais.some((item) => String(item.id) === id)
        ? atuais.filter((item) => String(item.id) !== id)
        : [...atuais, imovel];
    });
  }

  function dadosComparacao(imovel) {
    const cenario = cenariosSelecionados[imovel.id] || null;
    const analise = cenario
      ? analiseDoCenario(imovel, cenario)
      : analiseFinanceira(imovel, custosArremate[imovel.id] || {});
    const score = calcularScoreOportunidade(imovel, custosArremate[imovel.id] || {}, cenario);
    const faltantes = cenario
      ? (cenario.custos_nao_informados || [])
      : [
          ["comissao_leiloeiro", "comissao", "Comissão do leiloeiro"], ["itbi", "itbi", "ITBI"],
          ["registro", "registro", "Registro"], ["outros_custos", "outrosCustos", "Outros custos"],
          ["custo_venda", "custoVenda", "Custos de venda"], ["custo_reforma", "custoReforma", "Reforma"],
        ].filter(([campo, personalizado]) => imovel[campo] == null && custosArremate[imovel.id]?.[personalizado] == null)
         .map(([, , rotulo]) => rotulo);
    return { analise, score, faltantes, cenario };
  }

  // =========================================================
  // FAVORITOS
  // =========================================================

  function alternarFavorito(imovel) {
    const id = imovel?.id;

    if (id === null || id === undefined) {
      return;
    }

    setFavoritos((atuais) => {
      const jaFavoritado = atuais.some(
        (favoritoId) => String(favoritoId) === String(id)
      );

      const novoEstado = jaFavoritado
        ? atuais.filter(
            (favoritoId) => String(favoritoId) !== String(id)
          )
        : [...atuais, id];

      return novoEstado;
    });
  }

  // =========================================================
  // JSX
  // =========================================================

  const custosDetalhes =
    imovelDetalhes
      ? custosArremate[imovelDetalhes.id] || {}
      : {};
  const cenarioDetalhes = imovelDetalhes
    ? cenariosSelecionados[imovelDetalhes.id] || null
    : null;

  const scoreDetalhes = imovelDetalhes
    ? detalhesDoScore(
        imovelDetalhes,
        custosDetalhes,
        cenarioDetalhes
      )
    : null;

  const oportunidadeDetalhes = scoreDetalhes;

  const decisaoDetalhes = imovelDetalhes
    ? decisaoDaOportunidade(
        imovelDetalhes,
        custosDetalhes,
        cenarioDetalhes
      )
    : null;
  const IconeDecisao = decisaoDetalhes?.Icone || AlertTriangle;

  const analiseDetalhes = imovelDetalhes
    ? cenarioDetalhes
      ? analiseDoCenario(imovelDetalhes, cenarioDetalhes)
      : analiseFinanceira(imovelDetalhes, custosArremate[imovelDetalhes.id] || {})
    : null;

  function valorInputFinanceiro(valor) {
    const numero = Number(valor);

    if (!Number.isFinite(numero)) {
      return "";
    }

    return numero.toFixed(2);
  }

  function atualizarCustoArremate(campo, valor) {
    if (!imovelDetalhes) return;

    setCustosArremate((atuais) => ({
      ...atuais,
      [imovelDetalhes.id]: {
        ...atuais[imovelDetalhes.id],
        [campo]: Math.max(0, Number(valor) || 0),
      },
    }));
  }

  const imovelDetalhesId = imovelDetalhes?.id;
  const atualizarCenarioSelecionado = useCallback((cenario) => {
    if (imovelDetalhesId == null) return;
    setCenariosSelecionados((atuais) => {
      const idAtual = atuais[imovelDetalhesId]?.id ?? null;
      const idNovo = cenario?.id ?? null;
      if (String(idAtual) === String(idNovo)) return atuais;
      return { ...atuais, [imovelDetalhesId]: cenario };
    });
  }, [imovelDetalhesId]);

  async function abrirDetalhes(imovel) {
    // A foto do card já foi carregada no frontend. Ao abrir os detalhes,
    // começamos por ela e, se a URL falhar, avançamos automaticamente
    // para a próxima foto já coletada, sem recriar/substituir a galeria.
    setFotoDetalhesAtiva(0);

    // Mostra imediatamente os dados já carregados na lista.
    // As fotos da Caixa já estão persistidas/coletadas e não podem ser
    // substituídas por URLs diferentes vindas da resposta de detalhes.
    const fotosOriginais = fotosDoImovel(imovel);
    setImovelDetalhes(imovel);

    try {
      const resposta = await fetch(`${API_URL}/imoveis/${imovel.id}`);

      if (!resposta.ok) {
        throw new Error(`Não foi possível carregar os detalhes (${resposta.status}).`);
      }

      const detalhes = await resposta.json();
      const fotosDetalhes = fotosDoImovel(detalhes);

      // A foto que já funciona no card fica SEMPRE em primeiro lugar.
      // As fotos retornadas pelo detalhe são apenas acrescentadas à galeria.
      const fotosFinais = [...new Set([
        ...fotosOriginais,
        ...fotosDetalhes,
      ])];

      const detalhesFinais = {
        ...imovel,
        ...detalhes,
        imagens: fotosFinais,
        imagem: fotosFinais[0] || detalhes.imagem || imovel.imagem || null,
      };

      setImovelDetalhes(detalhesFinais);

      // Atualiza somente os dados do imóvel. A galeria existente no frontend
      // é preservada e não é recriada nem substituída.
      setImoveis((atuais) =>
        atuais.map((item) => {
          if (item.id !== detalhesFinais.id) return item;

          const fotosItem = fotosDoImovel(item);
          const fotosMescladas = [...new Set([
            ...fotosItem,
            ...fotosFinais,
          ])];

          return {
            ...item,
            ...detalhesFinais,
            imagens: fotosMescladas,
            imagem: fotosMescladas[0] || item.imagem || null,
          };
        })
      );
    } catch (erro) {
      console.error("Erro ao carregar detalhes do imóvel:", erro);
      // Se a rota de detalhes falhar, o modal continua usando exatamente
      // o imóvel que já estava carregado no frontend.
      setImovelDetalhes(imovel);
    }
  }

  if (verificandoAutenticacao) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1>Radar Leilão</h1>
          <p>Verificando sessão...</p>
        </div>
      </div>
    );
  }

  if (!token || !usuario) {
    return (
      <Login
        onLogin={(novoToken) => {
          setToken(novoToken);
          setVerificandoAutenticacao(true);
        }}
      />
    );
  }

  if (window.location.pathname === "/admin") {
    if (!ehAdministrador) {
      return (
        <div className="login-page">
          <div className="login-card">
            <h1>Radar Leilão</h1>
            <p>Acesso permitido apenas para administradores.</p>

            <button
              type="button"
              onClick={() => {
                window.location.href = "/";
              }}
            >
              Voltar
            </button>
          </div>
        </div>
      );
    }

    return <Admin usuario={usuario} onLogout={sair} />;
  }

  return (
    <div 
            
    className="app">

            {/* HEADER */}
        <header className="header">
          <div className="container header-content">

            <div className="logo">
              <div className="logo-icon">
                <Gavel size={24} />
              </div>

              <div>
                <h1>Radar Leilão</h1>
                <span>
                  Encontre oportunidades
                </span>
              </div>
            </div>

            <div className="header-account">
              <span className="user-role-badge">
                {ROTULOS_PAPEL[papel] || "Papel não configurado"}
              </span>
              {papel === "cliente" && (
                <nav className="cliente-navigation" aria-label="Navegação do cliente">
                  <a href="#meu-perfil">Meu perfil</a>
                  <a href="#minhas-oportunidades">Minhas oportunidades</a>
                  <a href="#alertas">Alertas</a>
                  <a href="#consultoria">Dúvidas sobre leilão</a>
                </nav>
              )}
              {papel === "corretor" && (
                <nav className="cliente-navigation" aria-label="Navegação do corretor">
                  <a href="#painel-corretor">Minhas oportunidades</a>
                  <a href="#perfil-corretor">Meu perfil</a>
                  <a href="#alertas">Alertas</a>
                  <a href="#consultoria">Dúvidas sobre leilão</a>
                </nav>
              )}
              {ehAdministrador && (
                <a className="header-admin-link" href="/admin">
                  Administração
                </a>
              )}
              <button type="button" className="header-logout" onClick={sair}>
                <LogOut size={16} />
                Sair
              </button>
              <span className="header-status">
                <span className="status-dot" />
                Sistema online
              </span>
            </div>

          </div>
        </header>

        {(papel === "cliente" || papel === "corretor") && <Alertas token={token} />}

        {papel === "cliente" && (
          <>
            <section id="meu-perfil" className="container cliente-profile-section">
              <div className="cliente-profile-card">
                <div className="cliente-profile-heading">
                  <span className="section-kicker">MINHA CONTA</span>
                  <h2>Meu perfil</h2>
                </div>
                <dl className="cliente-profile-details">
                  <div>
                    <dt>Nome</dt>
                    <dd>{usuario.nome || "Não informado"}</dd>
                  </div>
                  <div>
                    <dt>E-mail</dt>
                    <dd>{usuario.email || "Não informado"}</dd>
                  </div>
                  <div>
                    <dt>Tipo</dt>
                    <dd>{ROTULOS_PAPEL[usuario.tipo] || usuario.tipo || "Não informado"}</dd>
                  </div>
                </dl>
              </div>
            </section>

            <div className="container">
              <MinhasOportunidades
                usuario={usuario}
                token={token}
                onAbrirImovel={async (imovelId) => {
                  const imovelEncontrado = imoveis.find(
                    (item) => String(item.id) === String(imovelId)
                  );

                  if (imovelEncontrado) {
                    setImovelDetalhes(imovelEncontrado);
                    return;
                  }

                  try {
                    const resposta = await fetch(
                      `${API_URL}/imoveis/${imovelId}`,
                      {
                        headers: {
                          Authorization: `Bearer ${token}`,
                        },
                      }
                    );

                    if (!resposta.ok) {
                      throw new Error("Não foi possível carregar o imóvel.");
                    }

                    const imovel = await resposta.json();

                    setImovelDetalhes(imovel);
                  } catch (error) {
                    console.error("Erro ao abrir imóvel:", error);
                  }
                }}
              />
            </div>
          </>
        )}

        {papel === "corretor" && (
          <>
            <section id="perfil-corretor" className="container cliente-profile-section">
              <div className="cliente-profile-card">
                <div className="cliente-profile-heading">
                  <span className="section-kicker">MINHA CONTA</span>
                  <h2>Meu perfil</h2>
                </div>
                <dl className="cliente-profile-details">
                  <div><dt>Nome</dt><dd>{usuario.nome || "Não informado"}</dd></div>
                  <div><dt>E-mail</dt><dd>{usuario.email || "Não informado"}</dd></div>
                  <div><dt>Tipo</dt><dd>Corretor</dd></div>
                </dl>
              </div>
            </section>
            <Corretor
              usuario={usuario}
              token={token}
              onAbrirOportunidade={async (oportunidade) => {
                setOportunidadeSelecionada(oportunidade);
                const existente = imoveis.find(
                  (item) => String(item.id) === String(oportunidade.imovel_id)
                );
                if (existente) {
                  setImovelDetalhes(existente);
                  return;
                }
                try {
                  const resposta = await fetch(`${API_URL}/imoveis/${oportunidade.imovel_id}`, {
                    headers: { Authorization: `Bearer ${token}` },
                  });
                  if (!resposta.ok) throw new Error("Não foi possível carregar o imóvel.");
                  setImovelDetalhes(await resposta.json());
                } catch (error) {
                  setOportunidadeSelecionada(null);
                  console.error("Erro ao abrir oportunidade atribuída:", error);
                }
              }}
            />
          </>
        )}

        {/* HERO */}
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

      {/* CONTEÚDO */}
      <main className="container main">
        <StatusCaixa usuario={usuario} />

        {/* BARRA */}
        <div className="toolbar">

          <div className="toolbar-left">

            <button
              type="button"
              className="filter-button"
              onClick={() =>
                setFiltrosAbertos(
                  (valor) => !valor
                )
              }
            >
              <SlidersHorizontal size={18} />
              Filtros
              {quantidadeFiltrosAtivos() > 0 && (
                <span className="filter-count">
                  {quantidadeFiltrosAtivos()}
                </span>
              )}
            </button>

            {papel !== "corretor" && <button
              type="button"
              className={`favorites-toggle ${
                mostrarFavoritos ? "active" : ""
              }`}
              onClick={() => setMostrarFavoritos(!mostrarFavoritos)}
              aria-pressed={mostrarFavoritos
              }
            >
              ♡ Favoritos ({favoritos.length})
            </button>}

            <span className="result-count">
              {loading
                ? "Carregando..."
                : `${total} imóveis encontrados`}
            </span>

          </div>

          <div className="sort">

            <ArrowDownUp size={17} />

            <select
              value={ordenacao}
             onChange={(event) => {
              setPagina(1);
              setOrdenacao(event.target.value);
            }}
            >

              <option value="score">
                Melhores oportunidades
              </option>

              <option value="desconto">
                Maior desconto
              </option>

              <option value="menor-preco">
                Menor preço
              </option>

              <option value="economia-m2">
                Maior economia por m²
              </option>

              <option value="maior-area">
                Maior área
              </option>

              <option value="mais-recentes">
                Próximo leilão
              </option>
            </select>

          </div>

        </div>

        {/* FILTROS */}
        {filtrosAbertos && (
          <div className="filters-panel">

            <div className="filter-group">
              <label>Status do leilão</label>

              <select
                value={statusLeilao}
                onChange={(event) => {
                  setStatusLeilao(event.target.value);
                  setPagina(1);
                }}
              >
                <option value="ativos">🟢 Ativos</option>
                <option value="encerrados">🔴 Encerrados</option>
                <option value="sem_data">⚪ Sem data</option>
                <option value="todos">📋 Todos</option>
              </select>
            </div>

            <div className="filter-group">

              <label>Estado</label>

              <select
                value={estado}
                onChange={(event) =>
                  setEstado(
                    event.target.value
                  )
                }
              >
            <option value="">
              Todos
            </option>

            <option value="AC">
              Acre
            </option>

            <option value="AL">
              Alagoas
            </option>

            <option value="AP">
              Amapá
            </option>

            <option value="AM">
              Amazonas
            </option>

            <option value="BA">
              Bahia
            </option>

            <option value="CE">
              Ceará
            </option>

            <option value="DF">
              Distrito Federal
            </option>

            <option value="ES">
              Espírito Santo
            </option>

            <option value="GO">
              Goiás
            </option>

            <option value="MA">
              Maranhão
            </option>

            <option value="MT">
              Mato Grosso
            </option>

            <option value="MS">
              Mato Grosso do Sul
            </option>

            <option value="MG">
              Minas Gerais
            </option>

            <option value="PA">
              Pará
            </option>

            <option value="PB">
              Paraíba
            </option>

            <option value="PR">
              Paraná
            </option>

            <option value="PE">
              Pernambuco
            </option>

            <option value="PI">
              Piauí
            </option>

            <option value="RJ">
              Rio de Janeiro
            </option>

            <option value="RN">
              Rio Grande do Norte
            </option>

            <option value="RS">
              Rio Grande do Sul
            </option>

            <option value="RO">
              Rondônia
            </option>

            <option value="RR">
              Roraima
            </option>

            <option value="SC">
              Santa Catarina
            </option>

            <option value="SP">
              São Paulo
            </option>

            <option value="SE">
              Sergipe
            </option>

            <option value="TO">
              Tocantins
            </option>
              </select>

            </div>

            <div className="filter-group">

              <label>Tipo</label>

              <select
                value={tipo}
                onChange={(event) =>
                  setTipo(
                    event.target.value
                  )
                }
              >
                <option value="">
                  Todos
                </option>

                <option value="Casa">
                  Casa
                </option>

                <option value="Apartamento">
                  Apartamento
                </option>

                <option value="Terreno">
                  Terreno
                </option>

                <option value="Comercial">
                  Comercial
                </option>
              </select>

            </div>

            <div className="filter-group">

              <label>
                Desconto mínimo (%)
              </label>

              <input
                type="number"
                min="0"
                placeholder="Ex: 30"
                value={descontoMinimo}
                onChange={(event) =>
                  setDescontoMinimo(
                    event.target.value
                  )
                }
              />

            </div>

            <div className="filter-group">

              <label>
                Valor máximo
              </label>

              <input
                type="number"
                min="0"
                placeholder="Ex: 300000"
                value={valorMaximo}
                onChange={(event) =>
                  setValorMaximo(
                    event.target.value
                  )
                }
              />

            </div>

            <div className="filter-group">
              <label>Área mínima (m²)</label>

              <input
                type="number"
                min="0"
                placeholder="Ex: 40"
                value={areaMin}
                onChange={(event) =>
                  setAreaMin(event.target.value)
                }
              />
            </div>

            <div className="filter-group">
              <label>Área máxima (m²)</label>

              <input
                type="number"
                min="0"
                placeholder="Ex: 150"
                value={areaMax}
                onChange={(event) =>
                  setAreaMax(event.target.value)
                }
              />
            </div>

            <div className="filter-group">
              <label>Quartos</label>

              <input
                type="number"
                min="0"
                placeholder="Ex: 2"
                value={quartos}
                onChange={(event) =>
                  setQuartos(event.target.value)
                }
              />
            </div>

            <div className="filter-group">
              <label>Banheiros</label>

              <input
                type="number"
                min="0"
                placeholder="Ex: 2"
                value={banheiros}
                onChange={(event) =>
                  setBanheiros(event.target.value)
                }
              />
            </div>

            <div className="filter-group">
              <label>Vagas</label>

              <input
                type="number"
                min="0"
                placeholder="Ex: 1"
                value={vagas}
                onChange={(event) =>
                  setVagas(event.target.value)
                }
              />
            </div>

            <div className="filter-actions">

              <button
                type="button"
                className="clear-button"
                onClick={limparFiltros}
              >
                <X size={16} />
                Limpar
              </button>

              <button
                type="button"
                className="apply-button"
                onClick={pesquisar}
              >
                Aplicar filtros
              </button>

            </div>

          </div>
        )}

        {/* ERRO */}
        {erro && (
          <div className="error-box">
            <strong>Erro</strong>
            <span>{erro}</span>
          </div>
        )}

        {/* LOADING */}
        {loading && (
          <div className="loading">

            <div className="spinner" />

            <p>
              Carregando oportunidades...
            </p>

          </div>
        )}

        {/* SEM RESULTADOS */}
        {!loading &&
          !erro &&
          listaRenderizadaRadar.length === 0 && (
            <div className="empty">

              <Building2 size={48} />

              <h3>
                Nenhum imóvel encontrado
              </h3>

              <p>
                Tente alterar os filtros
                da pesquisa.
              </p>

            </div>
          )}

        {/* GRID */}
        {!loading &&
          listaRenderizadaRadar.length > 0 && (

            <>
            {imoveisComparacao.length > 0 && (
              <section className="comparison-panel" aria-labelledby="comparison-title">
                <header className="comparison-header">
                  <div><span className="fluxo-kicker">ANÁLISE LADO A LADO</span><h3 id="comparison-title">Comparação de oportunidades</h3><p>Os valores usam o cenário salvo selecionado em cada imóvel quando disponível.</p></div>
                  <button type="button" onClick={() => setImoveisComparacao([])}>Limpar seleção</button>
                </header>
                <div className="comparison-scroll">
                  <table className="comparison-table">
                    <thead><tr><th scope="col">Indicador</th>{imoveisComparacao.map((item) => <th scope="col" key={item.id}><strong>{item.titulo || "Imóvel"}</strong><span>{item.cidade || "Cidade não informada"}{item.estado ? ` · ${item.estado}` : ""}</span><button type="button" onClick={() => alternarComparacao(item)} aria-label={`Remover ${item.titulo || "imóvel"} da comparação`}>Remover</button></th>)}</tr></thead>
                    <tbody>{[
                      ["Preço de aquisição / leilão", (item, dados) => dinheiro(dados.cenario ? dados.cenario.preco_aquisicao : dados.analise.leilao)],
                      ["Investimento total estimado", (item, dados) => dinheiro(dados.analise.custoInvestimento)],
                      ["Revenda esperada", (item, dados) => dinheiro(dados.analise.valorRevenda)],
                      ["Lucro estimado", (item, dados) => dinheiro(dados.analise.lucroRealEstimado)],
                      ["ROI estimado", (item, dados) => dados.faltantes.length ? "Indisponível: custos pendentes" : Number.isFinite(dados.analise.retornoSobreInvestimento) ? `${dados.analise.retornoSobreInvestimento.toFixed(2).replace(".", ",")}%` : "Indisponível"],
                      ["Margem sobre revenda", (item, dados) => dados.faltantes.length ? "Indisponível: custos pendentes" : Number.isFinite(dados.analise.margemSeguranca) ? `${dados.analise.margemSeguranca.toFixed(2).replace(".", ",")}%` : "Indisponível"],
                      ["Desconto sobre avaliação", (item) => { const desconto = calcularDesconto(item); return desconto == null ? "Indisponível" : `${desconto.toFixed(2).replace(".", ",")}%`; }],
                      ["Score existente", (item, dados) => `${dados.score.valor}/100 · ${dados.score.texto}`],
                    ].map(([rotulo, valor]) => <tr key={rotulo}><th scope="row">{rotulo}</th>{imoveisComparacao.map((item) => { const dados = dadosComparacao(item); return <td key={item.id}>{valor(item, dados)}</td>; })}</tr>)}
                      <tr><th scope="row">Custos ausentes / por confirmar</th>{imoveisComparacao.map((item) => { const { faltantes, cenario } = dadosComparacao(item); return <td key={item.id}>{faltantes.length ? <><strong className="comparison-unknown">A confirmar</strong><span>{faltantes.join(", ")}</span>{cenario && <small>O cenário pode assumir zero nos campos ausentes; valores não confirmados não são tratados como conhecidos.</small>}</> : <span>Sem custos pendentes identificados</span>}</td>; })}</tr>
                    </tbody>
                  </table>
                </div>
                <p className="comparison-note">Na análise padrão, alguns custos usam estimativas predefinidas. Campos opcionais ausentes aparecem como pendentes; confirme-os antes de confiar no resultado.</p>
              </section>
            )}

            <div className="imoveis-grid">

              {listaRenderizadaRadar.map((imovel) => {
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
              )}

            </div>
            </>
          )}

        {/* PAGINAÇÃO */}
        {!loading &&
          !erro &&
          paginas > 1 && (

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

          )}

      </main>

      {(papel === "cliente" || papel === "corretor") && (
        <Consultoria token={token} />
      )}

      {/* GALERIA */}
      {galeriaAberta && (() => {
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
      })()}

      {/* DETALHES DO IMÓVEL */}
      {imovelDetalhes && (
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
                <div>
                  <span>Valor do leilão</span>
                  <strong>{dinheiro(imovelDetalhes.valor_leilao)}</strong>
                </div>
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
      )}
    </div>
  );
}

export default App;
