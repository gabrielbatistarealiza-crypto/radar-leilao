import { useEffect, useMemo, useState } from "react";
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
} from "lucide-react";

import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [imoveis, setImoveis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

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


  const alternarFavoritos = (imovel) => {
    const id = imovel?.id;
    if (id == null) return;

    setFavoritos((atuais) => {
      const jaFavoritado = atuais.some(
        (favoritoId) => String(favoritoId) === String(id)
      );

      return jaFavoritado
        ? atuais.filter(
            (favoritoId) => String(favoritoId) !== String(id)
          )
        : [...atuais, id];
    });
  };

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
  const [imovelDetalhes, setImovelDetalhes] = useState(null);
  const [custosArremate, setCustosArremate] = useState({});
  const [pesquisaVersion, setPesquisaVersion] = useState(0);



  useEffect(() => {
    localStorage.setItem(
      "radar-leilao-favoritos",
      JSON.stringify(favoritos)
    );
  }, [favoritos]);

  // =========================================================
  // FORMATA??O
  // =========================================================

  function dinheiro(valor) {
    if (valor === null || valor === undefined || valor === "") {
      return "NÃ£o informado";
    }

    const numero = Number(valor);

    if (!Number.isFinite(numero)) {
      return "NÃ£o informado";
    }

    return numero.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
    });
  }

  function formatarData(data) {
    if (!data) return "NÃ£o informada";

    const valor = new Date(`${data}T00:00:00`);

    return Number.isNaN(valor.getTime())
      ? "NÃ£o informada"
      : valor.toLocaleDateString("pt-BR");
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

  function calcularScoreOportunidade(imovel) {
  const desconto = calcularDesconto(imovel);
  const economia = calcularEconomia(imovel);

  const analise = analiseFinanceira(imovel);

  const economiaPorM2 =
    imovel.economia_m2 !== null && imovel.economia_m2 !== undefined
      ? Number(imovel.economia_m2)
      : null;

  // =====================================================
  // 1. DESCONTO â€” 40 PONTOS
  // =====================================================

  const pontosDesconto =
    desconto !== null
      ? Math.min(40, Math.max(0, Math.round(desconto)))
      : 0;

  // =====================================================
  // 2. ECONOMIA TOTAL â€” 20 PONTOS
  // =====================================================

  let pontosEconomia = 0;

  if (economia != null && economia > 0) {
    if (economia >= 100000) {
      pontosEconomia = 20;
    } else if (economia >= 50000) {
      pontosEconomia = 16;
    } else if (economia >= 30000) {
      pontosEconomia = 12;
    } else if (economia >= 15000) {
      pontosEconomia = 8;
    } else if (economia >= 5000) {
      pontosEconomia = 4;
    }
  }

  // =====================================================
  // 3. ECONOMIA POR mÂ² â€” 15 PONTOS
  // =====================================================

  let pontosEconomiaM2 = 0;

  if (economiaPorM2 != null && economiaPorM2 > 0) {
    if (economiaPorM2 >= 2000) {
      pontosEconomiaM2 = 15;
    } else if (economiaPorM2 >= 1500) {
      pontosEconomiaM2 = 12;
    } else if (economiaPorM2 >= 1000) {
      pontosEconomiaM2 = 9;
    } else if (economiaPorM2 >= 500) {
      pontosEconomiaM2 = 6;
    } else if (economiaPorM2 >= 250) {
      pontosEconomiaM2 = 3;
    }
  }

  // =====================================================
  // 4. DADOS ESSENCIAIS â€” 15 PONTOS
  // =====================================================

  const temDesconto = desconto !== null;
  const temArea = Number(
    imovel?.area_util ?? imovel?.area ?? 0
  ) > 0;

  const temLocalizacao = Boolean(
    imovel?.cidade && imovel?.estado
  );

  const temValores = Boolean(
    Number(imovel?.valor_avaliacao) > 0 &&
    Number(imovel?.valor_leilao) > 0
  );

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
  // 5. DATA DO LEILÃƒO â€” 10 PONTOS
  // =====================================================

  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  const datasLeilao = [
  imovel?.data_primeiro_leilao,
  imovel?.data_segundo_leilao,
]
  .filter(Boolean)
  .map((data) => {
    const d = new Date(data);
    d.setHours(0, 0, 0, 0);
    return d;
  })
  .filter((data) => !Number.isNaN(data.getTime()))
  .sort((a, b) => a - b);

const datasFuturas = datasLeilao.filter((data) => data >= hoje);

const proximaDataLeilao =
  datasFuturas.length > 0 ? datasFuturas[0] : null;

const leilaoJaRealizado =
  datasLeilao.length > 0 && !proximaDataLeilao;

let pontosData = 0;
let diasAteLeilao = null;

if (proximaDataLeilao) {
  diasAteLeilao = Math.ceil(
    (proximaDataLeilao - hoje) / (1000 * 60 * 60 * 24)
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
  // SCORE FINAL
  // =====================================================

  const valor = Math.min(
    100,
    pontosDesconto +
      pontosEconomia +
      pontosEconomiaM2 +
      pontosDados +
      pontosData
  );

  // =====================================================
  // CLASSIFICAÃ‡ÃƒO
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
    dadosCompletos,
    diasAteLeilao,
    leilaoJaRealizado,
    proximaDataLeilao,
  };
}

  function decisaoDaOportunidade(imovel) {
    const score = calcularScoreOportunidade(imovel);
    const desconto = calcularDesconto(imovel);

    const ocupado = imovel?.ocupado;

    // =====================================================
    // IMÃ“VEL CONFIRMADAMENTE OCUPADO
    // =====================================================

    if (ocupado === true) {
      return {
        classe: "evitar",
        titulo: "Risco elevado",
        descricao:
          "ImÃ³vel ocupado. Avalie cuidadosamente os custos, prazo e riscos de desocupaÃ§Ã£o antes de arrematar.",
        Icone: AlertTriangle
      };
    }

    // LEILÃ•ES JÃ ENCERRADOS
    const alertas = alertasDoImovel(imovel);

    const leiloesEncerrados = alertas.some(
      (alerta) => alerta.tipo === "danger"
    );

    if (leiloesEncerrados) {
      return {
        classe: "atencao",
        titulo: "LeilÃ£o sem oportunidade de compra no momento",
        descricao:
          "O imÃ³vel apresenta potencial financeiro, mas todos os leilÃµes identificados jÃ¡ foram realizados. Ã‰ necessÃ¡rio verificar se haverÃ¡ nova oferta ou atualizaÃ§Ã£o do edital.",
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
          "NÃ£o hÃ¡ informaÃ§Ãµes suficientes para considerar este imÃ³vel uma boa oportunidade.",
        Icone: CircleX
      };
    }

    // LEILÃƒO ACONTECE HOJE
    const leilaoHoje = alertas.some(
      (alerta) => alerta.texto === "LeilÃ£o acontece hoje"
    );

    if (leilaoHoje) {
      return {
        classe: "atencao",
        titulo: "AÃ§Ã£o imediata necessÃ¡ria",
        descricao:
          "O leilÃ£o acontece hoje. Confira imediatamente o edital, horÃ¡rio, condiÃ§Ãµes de pagamento e documentaÃ§Ã£o antes de participar.",
        Icone: AlertTriangle
      };
    }

    // LEILÃƒO PRÃ“XIMO
    const leilaoProximo = alertas.find(
      (alerta) =>
        alerta.tipo === "warning" &&
        alerta.texto.startsWith("PrÃ³ximo leilÃ£o em")
    );

    if (leilaoProximo && score.valor >= 80) {
      return {
        classe: "vale",
        titulo: "Vale a pena analisar",
        descricao:
          `${leilaoProximo.texto}. Excelente potencial pelos dados disponÃ­veis. Verifique o edital, matrÃ­cula e custos antes de arrematar.`,
        Icone: CircleCheck
      };
    }

    if (leilaoProximo && score.valor >= 65) {
      return {
        classe: "boa",
        titulo: "Boa oportunidade para analisar",
        descricao:
          `${leilaoProximo.texto}. O imÃ³vel apresenta bom potencial, mas Ã© importante verificar o edital, matrÃ­cula e custos antes de arrematar.`,
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
      "Excelente potencial pelos dados disponÃ­veis, mas ainda Ã© necessÃ¡rio confirmar as informaÃ§Ãµes do imÃ³vel, edital e custos antes de arrematar.",
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
      "Bom potencial pelos dados disponÃ­veis, mas Ã© necessÃ¡rio confirmar as informaÃ§Ãµes do imÃ³vel, edital e custos antes de arrematar.",
    Icone: AlertTriangle
  };
}


    // OPORTUNIDADE MÃ‰DIA
    // =====================================================

    return {
      classe: "atencao",
      titulo: "AtenÃ§Ã£o",
      descricao:
        "O imÃ³vel apresenta potencial, mas Ã© necessÃ¡rio analisar os detalhes antes de arrematar.",
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
    ]
      .filter(Boolean)
      .map((data) => {
        const dataLeilao = new Date(`${data}T00:00:00`);
        return Number.isNaN(dataLeilao.getTime())
          ? null
          : dataLeilao;
      })
      .filter(Boolean)
      .sort((a, b) => a - b);

    const dataFutura = datas.find((data) => data >= hoje);

    // SEM LEILÃƒO FUTURO
    if (!dataFutura) {
      return {
        nivel: "fora",
        label: "LEILÃ•ES ENCERRADOS",
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
      texto: "Sem fotos disponÃ­veis",
    });
  }

  // DATAS DOS LEILÃ•ES
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);

  const datas = [
    imovel?.data_primeiro_leilao,
    imovel?.data_segundo_leilao,
  ]
    .filter(Boolean)
    .map((data) => {
      const dataLeilao = new Date(`${data}T00:00:00`);
      return Number.isNaN(dataLeilao.getTime())
        ? null
        : dataLeilao;
    })
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
        texto: "LeilÃ£o acontece hoje",
      });
    } else if (dias <= 30) {
      alertas.push({
        tipo: "warning",
        texto: `PrÃ³ximo leilÃ£o em ${dias} dias`,
      });
    } else if (dias <= 90) {
      alertas.push({
        tipo: "info",
        texto: `PrÃ³ximo leilÃ£o em ${dias} dias`,
      });
    }
  } else if (datas.length > 0) {
    alertas.push({
      tipo: "danger",
      texto: "Todos os leilÃµes jÃ¡ realizados",
    });
  }

  // ÃREA
  if (!(Number(imovel?.area) > 0)) {
    alertas.push({
      tipo: "warning",
      texto: "Ãrea nÃ£o informada",
    });
  }

  // VALORES
  if (
    !(Number(imovel?.valor_avaliacao) > 0) ||
    !(Number(imovel?.valor_leilao) > 0)
  ) {
    alertas.push({
      tipo: "warning",
      texto: "Valores do imÃ³vel incompletos",
    });
  }

  // LOCALIZAÃ‡ÃƒO
  if (!imovel?.cidade || !imovel?.estado) {
    alertas.push({
      tipo: "warning",
      texto: "LocalizaÃ§Ã£o incompleta",
    });
  }

  return alertas;
}

function detalhesDoScore(imovel) {
  const score = calcularScoreOportunidade(imovel);
  const analise = analiseFinanceira(imovel);

  const financiamento = imovel?.aceita_financiamento;

  return {
    ...score,
    analise,
    condicoesCompra: [
      imovel?.ocupado !== undefined &&
        imovel?.ocupado !== null && {
          nome: "OcupaÃ§Ã£o",
          valor: imovel.ocupado ? "Ocupado" : "Desocupado",
        },

      imovel?.aceita_fgts !== undefined &&
        imovel?.aceita_fgts !== null && {
          nome: "FGTS",
          valor: imovel.aceita_fgts ? "Aceita" : "NÃ£o aceita",
        },

      financiamento !== undefined &&
        financiamento !== null && {
          nome: "Financiamento",
          valor: financiamento ? "Aceita" : "NÃ£o aceita",
        },
    ].filter(Boolean),
  };
}


  // =========================================================
  // FOTOS
  // =========================================================

  function fotosDoImovel(imovel) {
    if (Array.isArray(imovel.imagens)) {
      return imovel.imagens.filter(Boolean);
    }

    if (Array.isArray(imovel.imagem)) {
      return imovel.imagem.filter(Boolean);
    }

    if (imovel.imagem) {
      return [imovel.imagem];
    }

    return [];
  }

  function abrirGaleria(imovel) {
    const fotos = fotosDoImovel(imovel);

    if (fotos.length === 0) {
      return;
    }

    setFotoAtiva(0);
    setGaleriaAberta(imovel);
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
  // PAGINA??O
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
    try {
      setLoading(true);
      setErro("");

      const params = new URLSearchParams();

      params.append("pagina", String(pagina));
      params.append("tamanho_pagina", String(limite));

      params.append(
        "modalidade",
        "LeilÃ£o SFI - Edital Ãšnico"
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

      if (ordenacao === "score") {
        params.append("ordenar", "score");
        params.append("direcao", "desc");
      }

      if (ordenacao === "mais-recentes") {
        params.append("ordenar", "data");
        params.append("direcao", "asc");
      }

      console.log("PARAMETROS:", params.toString());
      console.log("CIDADE BUSCADA:", busca);
      console.log("ESTADO:", estado);
      console.log("MODALIDADE:", params.get("modalidade"));

      const url =
        `${API_URL}/imoveis/?${params.toString()}`;

      console.log("BUSCANDO:", url);

      const resposta = await fetch(url);

      if (!resposta.ok) {
        throw new Error(
          `Erro HTTP ${resposta.status}`
        );
      }

      const dados = await resposta.json();

      console.log(
        "RESPOSTA DA API:",
        dados
      );

      const listaImoveis = Array.isArray(dados.itens)
        ? dados.itens
        : Array.isArray(dados.items)
          ? dados.items
          : [];

      console.log("IMÃ“VEIS PARA RENDERIZAR:", listaImoveis.length);

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
      console.error(
        "ERRO AO CARREGAR IM?VEIS:",
        error
      );

      setErro(
        "NÃ£o foi possÃ­vel carregar os imÃ³veis."
      );

      setImoveis([]);
    } finally {
      setLoading(false);
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
  // ORDENA??O
  // =========================================================

  function calcularEconomiaPorM2(imovel) {
    const economia = calcularEconomia(imovel);
    const area = Number(imovel?.area);

    if (!Number.isFinite(area) || area <= 0) {
      return null;
    }

    return economia / area;
  }

  function dataMaisRecente(imovel) {
    const data =
      imovel?.data_segundo_leilao ||
      imovel?.data_primeiro_leilao;

    if (!data) {
      return null;
    }

    const timestamp = new Date(data).getTime();

    return Number.isFinite(timestamp) ? timestamp : null;
  }

  function compararNumeros(a, b, direcao = "desc") {
    const primeiro = Number(a);
    const segundo = Number(b);
    const primeiroValido = Number.isFinite(primeiro);
    const segundoValido = Number.isFinite(segundo);

    if (!primeiroValido && !segundoValido) return 0;
    if (!primeiroValido) return 1;
    if (!segundoValido) return -1;

    return direcao === "asc"
      ? primeiro - segundo
      : segundo - primeiro;
  }

  const imoveisOrdenados = imoveis;

  const imoveisExibidos =
    mostrarFavoritos
      ? imoveisOrdenados.filter(
        (imovel) =>
          favoritos.some(
            (id) => String(id) === String(imovel.id)
          )
      )
    : imoveisOrdenados;

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

  const scoreDetalhes = imovelDetalhes
    ? detalhesDoScore(imovelDetalhes)
    : null;
  const oportunidadeDetalhes = imovelDetalhes
    ? calcularScoreOportunidade(imovelDetalhes)
    : null;
  const decisaoDetalhes = imovelDetalhes
    ? decisaoDaOportunidade(imovelDetalhes)
    : null;
  const IconeDecisao = decisaoDetalhes?.Icone || AlertTriangle;

  const analiseDetalhes = imovelDetalhes
    ? analiseFinanceira(
        imovelDetalhes,
        custosArremate[imovelDetalhes.id] || {}
      )
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

  async function abrirDetalhes(imovel) {
    // Exibe os dados jÃ¡ disponÃ­veis imediatamente e, em seguida, busca o
    // detalhe completo. Para imÃ³veis Caixa, essa rota coleta fotos e datas.
    setImovelDetalhes(imovel);

    try {
      const resposta = await fetch(`${API_URL}/imoveis/${imovel.id}`);

      if (!resposta.ok) {
        throw new Error(`NÃ£o foi possÃ­vel carregar os detalhes (${resposta.status}).`);
      }

      const detalhes = await resposta.json();
      setImovelDetalhes(detalhes);

      // MantÃ©m a lista em memÃ³ria alinhada ao imÃ³vel enriquecido, evitando
      // nova consulta Ã  Caixa caso o modal seja aberto novamente.
      setImoveis((atuais) =>
        atuais.map((item) => (item.id === detalhes.id ? { ...item, ...detalhes } : item))
      );
    } catch (erro) {
      console.error("Erro ao carregar detalhes do imÃ³vel:", erro);
    }
  }

  return (
    <div className="app">

      {/* HEADER */}
      <header className="header">
        <div className="container header-content">

          <div className="logo">

            <div className="logo-icon">
              <Gavel size={24} />
            </div>

            <div>
              <h1>Radar leilÃ£o</h1>
              <span>
                Encontre oportunidades
              </span>
            </div>

          </div>

          <div className="header-status">
            <span className="status-dot" />
            Sistema online
          </div>

        </div>
      </header>

      {/* HERO */}
      <section className="hero">
        <div className="container">

          <div className="hero-text">

            <span className="hero-label">
              <Gavel size={16} />
              OPORTUNIDADES EM LEILÃƒâ€¢ES
            </span>

            <h2>
              Encontre imÃ³veis abaixo
              <br />
              <strong>
                do valor de mercado.
              </strong>
            </h2>

            <p>
              Pesquise imÃ³veis de leilÃ£o,
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
                placeholder="Digite cidade ou regiÃ£o..."
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

      {/* CONTEÃšDO */}
      <main className="container main">

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

            <button
              type="button"
              className={`favorites-toggle ${
                mostrarFavoritos ? "active" : ""
              }`}
              onClick={() => setMostrarFavoritos(!mostrarFavoritos)}
              aria-pressed={mostrarFavoritos
              }
            >
              â™¡ Favoritos ({favoritos.length})
            </button>

            <span className="result-count">
              {loading
                ? "Carregando..."
                : `${total} imÃ³veis encontrados`}
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
                Menor preÃ§o
              </option>

              <option value="economia-m2">
                Maior economia por mÂ²
              </option>

              <option value="maior-area">
                Maior Ã¡rea
              </option>

              <option value="mais-recentes">
                PrÃ³ximo leilÃ£o
              </option>
            </select>

          </div>

        </div>

        {/* FILTROS */}
        {filtrosAbertos && (
          <div className="filters-panel">

            <div className="filter-group">
              <label>Status do leilÃ£o</label>

              <select
                value={statusLeilao}
                onChange={(event) => {
                  setStatusLeilao(event.target.value);
                  setPagina(1);
                }}
              >
                <option value="ativos">ðŸŸ¢ Ativos</option>
                <option value="encerrados">ðŸ”´ Encerrados</option>
                <option value="sem_data">âšª Sem data</option>
                <option value="todos">ðŸ“‹ Todos</option>
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
              AmapÃ¡
            </option>

            <option value="AM">
              Amazonas
            </option>

            <option value="BA">
              Bahia
            </option>

            <option value="CE">
              CearÃ¡
            </option>

            <option value="DF">
              Distrito Federal
            </option>

            <option value="ES">
              EspÃ­rito Santo
            </option>

            <option value="GO">
              GoiÃ¡s
            </option>

            <option value="MA">
              MaranhÃ£o
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
              ParÃ¡
            </option>

            <option value="PB">
              ParaÃ­ba
            </option>

            <option value="PR">
              ParanÃ¡
            </option>

            <option value="PE">
              Pernambuco
            </option>

            <option value="PI">
              PiauÃ­
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
              RondÃ´nia
            </option>

            <option value="RR">
              Roraima
            </option>

            <option value="SC">
              Santa Catarina
            </option>

            <option value="SP">
              SÃ£o Paulo
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
                Desconto mÃ­nimo (%)
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
                Valor mÃ¡ximo
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
              <label>Ãrea mÃ­nima (mÂ²)</label>

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
              <label>Ãrea mÃ¡xima (mÂ²)</label>

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
          imoveisExibidos.length === 0 && (
            <div className="empty">

              <Building2 size={48} />

              <h3>
                Nenhum imÃ³vel encontrado
              </h3>

              <p>
                Tente alterar os filtros
                da pesquisa.
              </p>

            </div>
          )}

        {/* GRID */}
        {!loading &&
          imoveisExibidos.length > 0 && (

            <div className="imoveis-grid">

              {imoveisExibidos.map((imovel) => {
                const fotos = Array.isArray(imovel.imagens)
                  ? imovel.imagens
                  : imovel.imagem
                    ? [imovel.imagem]
                    : [];

                const economia =
                  imovel.valor_avaliacao && imovel.valor_leilao
                    ? imovel.valor_avaliacao - imovel.valor_leilao
                    : 0;

                const analise = analiseFinanceira(imovel);

                const descontoCalculado = calcularDesconto(imovel);

                const oportunidade = calcularScoreOportunidade(imovel);
                const decisao = decisaoDaOportunidade(imovel);
                const alertas = alertasDoImovel(imovel);
                const prioridade = prioridadeDoImovel(imovel);
                const IconeDecisao = decisao.Icone;
                const economiaPorM2 =
                  imovel.economia_m2 !== null && imovel.economia_m2 !== undefined
                    ? Number(imovel.economia_m2)
                    : null;
                const pontosDesconto = descontoCalculado === null
                  ? 0
                  : Math.min(40, Math.round(descontoCalculado));
                const pontosEconomia =
                  economia > 0
                    ? economia >= 100000
                      ? 20
                      : economia >= 50000
                        ? 16
                        : economia >= 30000
                          ? 12
                          : economia >= 15000
                            ? 8
                            : economia >= 5000
                              ? 4
                              : 0
                    : 0;
                const dadosCompletos = [
                  descontoCalculado !== null,
                  Number(imovel?.area) > 0,
                  Boolean(imovel?.cidade && imovel?.estado),
                  Boolean(
                    imovel?.data_primeiro_leilao || imovel?.data_segundo_leilao
                  ),
                ];
               const pontosDados =
                (dadosCompletos[0] ? 4 : 0) +
                (dadosCompletos[1] ? 4 : 0) +
                (dadosCompletos[2] ? 4 : 0) +
                (Boolean(imovel?.valor_avaliacao && imovel?.valor_leilao) ? 3 : 0);

                const hojeCard = new Date();
                hojeCard.setHours(0, 0, 0, 0);

                const datasLeilaoCard = [
                  imovel?.data_primeiro_leilao,
                  imovel?.data_segundo_leilao,
                ]
                  .filter(Boolean)
                  .map((data) => {
                    const d = new Date(data);
                    d.setHours(0, 0, 0, 0);
                    return d;
                  })
                  .filter((data) => !Number.isNaN(data.getTime()))
                  .sort((a, b) => a - b);

                const datasFuturasCard = datasLeilaoCard.filter(
                  (data) => data >= hojeCard
                );

                const proximaDataLeilaoCard =
                  datasFuturasCard.length > 0 ? datasFuturasCard[0] : null;

                const diasAteLeilaoCard = proximaDataLeilaoCard
                  ? Math.ceil(
                      (proximaDataLeilaoCard - hojeCard) /
                        (1000 * 60 * 60 * 24)
                    )
                  : null;

                let pontosDataCard = 0;

                if (diasAteLeilaoCard !== null) {
                  if (diasAteLeilaoCard <= 30) {
                    pontosDataCard = 10;
                  } else if (diasAteLeilaoCard <= 90) {
                    pontosDataCard = 8;
                  } else if (diasAteLeilaoCard <= 180) {
                    pontosDataCard = 5;
                  } else {
                    pontosDataCard = 2;
                  }
                }

                const condicoesCompra = [
                  imovel?.ocupado !== undefined && imovel?.ocupado !== null && {
                    nome: "OcupaÃ§Ã£o",
                    valor: imovel.ocupado ? "Ocupado" : "Desocupado",
                  },
                  imovel?.aceita_fgts !== undefined && imovel?.aceita_fgts !== null && {
                    nome: "FGTS",
                    valor: imovel.aceita_fgts ? "Aceita" : "NÃ£o aceita",
                  },
        imovel?.aceita_financiamento !== undefined && imovel?.aceita_financiamento !== null && {
            nome: "Financiamento",
            valor: imovel?.aceita_financiamento ? "Aceita" : "NÃ£o aceita",
        },
                ].filter(Boolean);

                return (
                  <article
                    className="card"
                    key={imovel.id}
                  >

                    {/* IMAGEM */}
                    <div className="card-image">

                      {/* FAVORITO */}
                      <button
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
                      </button>

                      {/* BADGE */}
                      <div className="auction-badge">
                        {"\u{1F528}"} LEILÃƒO SFI
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
                              "ImÃ³vel"
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
                          ImÃ³vel de leilÃ£o
                        </span>

                      </div>

                    </div>

                    {/* CONTEÃšDO */}
                    <div className="card-body">

                      {/* ALERTAS */}
                      {alertas.length > 0 && (
                        <div className="card-alerts">
                          {alertas.map((alerta, index) => (
                            <span
                              key={`${imovel.id}-alerta-${index}`}
                              className={`card-alert ${alerta.tipo}`}
                            >
                              {alerta.tipo === "danger"
                                ? "ðŸ”´"
                                : alerta.tipo === "warning"
                                  ? "âš ï¸"
                                  : "â„¹ï¸"}{" "}
                              {alerta.texto}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* T?TULO */}
                      <h3 className="card-title">
                        {imovel.titulo ||
                          "ImÃ³vel"}
                      </h3>

                      {/* LOCALIZA??O */}
                      <div className="location">

                        <MapPin size={16} />

                        <span>
                          {imovel.cidade ||
                            "Cidade nÃ£o informada"}

                          {imovel.estado
                            ? ` - ${imovel.estado}`
                            : ""}
                        </span>

                      </div>

                      {/* TIPO */}
                      <div className="property-type">

                        <Tag size={15} />

                        {imovel.tipo ||
                          "Tipo nÃ£o informado"}

                      </div>

                      {/* CARACTERÃSTICAS */}
                      {(imovel.area_util ||
                        imovel.quartos ||
                        imovel.banheiros ||
                        imovel.vagas) && (
                        <div className="property-features">

                          {imovel.area_util && (
                            <span>
                              <Ruler size={16} />
                              {imovel.area_util} mÂ²
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
                            ðŸ’° DESCONTO{" "}
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
                      {prioridade.nivel === "p1" && "ðŸ”¥"}
                      {prioridade.nivel === "p2" && "âš¡"}
                      {prioridade.nivel === "p3" && "ðŸ”Ž"}
                      {prioridade.nivel === "p4" && "ðŸ‘ï¸"}
                      {prioridade.nivel === "fora" && "â¸ï¸"}
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
                            Ver composiÃ§Ã£o do score
                          </summary>

                          <div className="score-factors">
                            <div className="score-factor">
                              <span>Desconto</span>
                              <strong>
                                {descontoCalculado === null
                                  ? "NÃ£o informado"
                                  : `${descontoCalculado.toFixed(2).replace(".", ",")}%`}
                              </strong>
                              <small>{pontosDesconto}/40 pontos</small>
                            </div>
                            <div className="score-factor">
                              <span>Economia total</span>
                              <strong>{economia > 0 ? dinheiro(economia) : "NÃ£o informado"}</strong>
                              <small>{pontosEconomia}/20 pontos</small>
                            </div>
                            <div className="score-factor">
                              <span>Economia por mÂ²</span>
                              <strong>
                                {economiaPorM2 !== null
                                  ? `${dinheiro(economiaPorM2)}/mÂ²`
                                  : "NÃ£o informado"}
                              </strong>
                              <small>Indicador complementar</small>
                            </div>
                            <div className="score-factor">

                              <div className="score-factor">
                                <span>Data do leilÃ£o</span>
                                <strong>
                                {proximaDataLeilaoCard
                                  ? `${diasAteLeilaoCard} dias`
                                  : "Todos realizados"}
                                </strong>
                                <small>{pontosDataCard}/10 pontos</small>
                              </div>
                              <span>Completude dos dados</span>
                              <strong>{dadosCompletos.filter(Boolean).length}/4 itens</strong>
                              <small>{pontosDados}/15 pontos</small>
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
                        aria-label={`DecisÃ£o da oportunidade: ${decisao.titulo}`}
                      >
                        <IconeDecisao size={18} aria-hidden="true" />
                        <div>
                          <span>DecisÃ£o da oportunidade</span>
                          <strong>{decisao.titulo}</strong>
                          <small>{decisao.descricao}</small>
                        </div>
                      </div>

                      {/* ECONOMIA */}
                      {economia > 0 && (

                        <div className="economy">

                          VocÃª economiza{" "}

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
                            <span>Valor/mÂ² avaliaÃ§Ã£o</span>
                            <strong>
                              {analise.valorM2Avaliacao
                                ? dinheiro(analise.valorM2Avaliacao)
                                : "NÃ£o informado"}
                            </strong>
                          </div>

                          <div className="financial-row">
                            <span>Valor/mÂ² leilÃ£o</span>
                            <strong>
                              {analise.valorM2Leilao
                                ? dinheiro(analise.valorM2Leilao)
                                : "NÃ£o informado"}
                            </strong>
                          </div>
                          {analise.valorM2Avaliacao && analise.valorM2Leilao && (
                            <div className="financial-saving">
                              Economia por mÂ²{" "}
                              <strong>
                                {imovel.economia_m2 !== null && imovel.economia_m2 !== undefined
                                  ? `${dinheiro(imovel.economia_m2)}/mÂ²`
                                  : "NÃ£o informado"}
                              </strong>
                            </div>
                          )}

                        </div>
                      )}

                      {/* ENDERE?O */}
                      {imovel.endereco && (

                        <div className="address">

                          <MapPin size={14} />

                          <span>
                            {imovel.endereco}
                          </span>

                        </div>

                      )}

                      {/* BOT?O */}
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

          )}

        {/* PAGINA??O */}
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
                â†
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
                â†’
              </button>

            </div>

          )}

      </main>

      {/* GALERIA */}
      {galeriaAberta && (

        <div
          className="gallery-modal"
          role="dialog"
          aria-modal="true"
          aria-label={`Fotos de ${galeriaAberta.titulo}`}
          onClick={() =>
            setGaleriaAberta(null)
          }
        >

          <div
            className="gallery-content"
            onClick={(event) =>
              event.stopPropagation()
            }
          >

            <button
              type="button"
              className="gallery-close"
              onClick={() =>
                setGaleriaAberta(null)
              }
              aria-label="Fechar galeria"
            >
              <X size={22} />
            </button>

            {fotosDoImovel(galeriaAberta).length > 1 && (
            <>
              <button
                type="button"
                className="gallery-nav gallery-prev"
                onClick={fotoAnterior}
                aria-label="Foto anterior"
              >
                â€¹
              </button>

              <button
                type="button"
                className="gallery-nav gallery-next"
                onClick={proximaFoto}
                aria-label="PrÃ³xima foto"
              >
                â€º
              </button>
            </>
          )}

            <img
              src={
                fotosDoImovel(
                  galeriaAberta
                )[fotoAtiva]
              }
              alt={
                galeriaAberta.titulo
              }
            />

            <div className="gallery-footer">

              <strong>
                {galeriaAberta.titulo}
              </strong>

              <span>
                {fotoAtiva + 1} de{" "}
                {
                  fotosDoImovel(
                    galeriaAberta
                  ).length
                }
              </span>

            </div>

            {fotosDoImovel(
              galeriaAberta
            ).length > 1 && (

                <div className="gallery-thumbnails">

                  {fotosDoImovel(
                    galeriaAberta
                  ).map(
                    (fotoUrl, indice) => (

                      <button
                        type="button"
                        className={
                          indice === fotoAtiva
                            ? "active"
                            : ""
                        }
                        key={`${fotoUrl}-${indice}`}
                        onClick={() =>
                          setFotoAtiva(
                            indice
                          )
                        }
                      >

                        <img
                          src={fotoUrl}
                          alt={`Foto ${indice + 1
                            }`}
                        />

                      </button>

                    )
                  )}

                </div>

              )}

          </div>

        </div>

      )}

      {/* DETALHES DO IM?VEL */}
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
                  aria-label={`Ver fotos de ${imovelDetalhes.titulo || "imÃ³vel"}`}
                >
                  <img
                    src={fotosDoImovel(imovelDetalhes)[0]}
                    alt={imovelDetalhes.titulo || "ImÃ³vel"}
                  />
                  <span>
                    <ImageIcon size={17} />
                    Ver {fotosDoImovel(imovelDetalhes).length} foto(s)
                  </span>
                </button>
              ) : (
                <div className="details-image-placeholder">
                  <Home size={50} />
                  <span>ImÃ³vel de leilÃ£o</span>
                </div>
              )}
            </div>

            <div className="details-body">
              <span className="auction-badge">LEILÃƒO SFI</span>

              <h2>{imovelDetalhes.titulo || "ImÃ³vel"}</h2>

              <div className="details-location">
                <MapPin size={17} />
                <span>
                  {imovelDetalhes.cidade || "Cidade nÃ£o informada"}
                  {imovelDetalhes.estado ? ` - ${imovelDetalhes.estado}` : ""}
                </span>
              </div>

              <button
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
              </button>

              <div className="details-discount">
                ðŸ’° DESCONTO <strong>
                  {(calcularDesconto(imovelDetalhes) || 0).toFixed(2).replace(".", ",")}% OFF
                </strong>
              </div>

              <div className="details-prices">
                <div>
                  <span>Valor de avaliaÃ§Ã£o</span>
                  <strong>{dinheiro(imovelDetalhes.valor_avaliacao)}</strong>
                </div>
                <div>
                  <span>Valor do leilÃ£o</span>
                  <strong>{dinheiro(imovelDetalhes.valor_leilao)}</strong>
                </div>
                <div>
                  <span>VocÃª economiza</span>
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
                        ? "NÃ£o informado"
                        : `${scoreDetalhes.desconto.toFixed(2).replace(".", ",")}%`}
                    </strong>
                    <small>{scoreDetalhes.pontosDesconto}/40 pontos</small>
                  </div>

                  <div className="score-factor">
                    <span>Economia total</span>
                    <strong>
                      {scoreDetalhes.economia > 0
                        ? dinheiro(scoreDetalhes.economia)
                        : "NÃ£o informado"}
                    </strong>
                    <small>{scoreDetalhes.pontosEconomia}/20 pontos</small>
                  </div>

                  <div className="score-factor">
                    <span>Economia por mÂ²</span>
                    <strong>
                      {scoreDetalhes.economiaPorM2 !== null
                        ? `${dinheiro(scoreDetalhes.economiaPorM2)}/mÂ²`
                        : "NÃ£o informado"}
                    </strong>
                    <small>{scoreDetalhes.pontosEconomiaM2}/15 pontos</small>
                  </div>

                  <div className="score-factor">
                    <span>Dados essenciais</span>
                    <strong>
                      {scoreDetalhes.dadosCompletos.filter(Boolean).length}/4 itens
                    </strong>
                    <small>{scoreDetalhes.pontosDados}/15 pontos</small>
                  </div>

                  <div className="score-factor">
                    <span>Data do leilÃ£o</span>
                    <strong>
                      {scoreDetalhes.leilaoJaRealizado
                        ? "LeilÃ£o jÃ¡ realizado"
                        : scoreDetalhes.diasAteLeilao !== null
                          ? `${scoreDetalhes.diasAteLeilao} dias`
                          : "NÃ£o informado"}
                    </strong>
                    <small>{scoreDetalhes.pontosData}/10 pontos</small>
                  </div>
                </div>
              </section>

              <section
                className={`decision-indicator details-decision ${decisaoDetalhes.classe}`}
                aria-label={`DecisÃ£o da oportunidade: ${decisaoDetalhes.titulo}`}
              >
                <IconeDecisao size={22} aria-hidden="true" />
                <div>
                  <span>DecisÃ£o da oportunidade</span>
                  <strong>{decisaoDetalhes.titulo}</strong>
                  <small>{decisaoDetalhes.descricao}</small>
                </div>
              </section>

              {/* ANÃLISE FINANCEIRA */}
              {analiseDetalhes && (
                <div className="financial-analysis">

                  <h3>AnÃ¡lise financeira</h3>

                  <div className="financial-grid">

                    <div className="financial-card">
                      <span>Valor/mÂ² avaliaÃ§Ã£o</span>
                      <strong>
                        {dinheiro(analiseDetalhes.valorM2Avaliacao)}
                      </strong>
                    </div>

                    <div className="financial-card">
                      <span>Valor/mÂ² leilÃ£o</span>
                      <strong>
                        {dinheiro(analiseDetalhes.valorM2Leilao)}
                      </strong>
                    </div>

                    <div className="financial-card">
                      <span>Economia por mÂ²</span>
                      <strong>
                        {dinheiro(
                          analiseDetalhes.valorM2Avaliacao -
                          analiseDetalhes.valorM2Leilao
                        )}
                      </strong>
                    </div>

                  </div>

                  <div className="financial-simulation">

                    <h4>SimulaÃ§Ã£o do investimento</h4>

                    <div className="financial-input-grid">

                      <label>
                        ComissÃ£o do leiloeiro
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
                            : "â€”"}
                        </strong>
                      </div>

                      <div>
                        <span>Margem de seguranÃ§a</span>
                        <strong>
                          {Number.isFinite(analiseDetalhes.margemSeguranca)
                            ? `${analiseDetalhes.margemSeguranca.toFixed(2).replace(".", ",")}%`
                            : "â€”"}
                        </strong>
                      </div>

                    </div>

                  </div>

                </div>
              )}

              <h3>Dados do leilÃ£o</h3>

              <div className="details-auction-grid">

                <div>
                  <span>1Âº leilÃ£o</span>
                  <strong>
                    {imovelDetalhes.data_primeiro_leilao
                      ? formatarData(imovelDetalhes.data_primeiro_leilao)
                      : "NÃ£o informado"}
                  </strong>
                </div>

                <div>
                  <span>2Âº leilÃ£o</span>
                  <strong>
                    {imovelDetalhes.data_segundo_leilao
                      ? formatarData(imovelDetalhes.data_segundo_leilao)
                      : "NÃ£o informado"}
                  </strong>
                </div>

                <div>
                  <span>Modalidade</span>
                  <strong>
                    {imovelDetalhes.modalidade || "NÃ£o informado"}
                  </strong>
                </div>

                <div>
                  <span>Valor de avaliaÃ§Ã£o</span>
                  <strong>
                    {Number.isFinite(Number(imovelDetalhes.valor_avaliacao))
                      ? Number(imovelDetalhes.valor_avaliacao).toLocaleString("pt-BR", {
                          style: "currency",
                          currency: "BRL",
                        })
                      : "NÃ£o informado"}
                  </strong>
                </div>

                <div>
                  <span>Valor do leilÃ£o</span>
                  <strong>
                    {Number.isFinite(Number(imovelDetalhes.valor_leilao))
                      ? Number(imovelDetalhes.valor_leilao).toLocaleString("pt-BR", {
                          style: "currency",
                          currency: "BRL",
                        })
                      : "NÃ£o informado"}
                  </strong>
                </div>

                <div>
                  <span>Ãrea</span>
                  <strong>
                    {imovelDetalhes.area
                      ? `${Number(imovelDetalhes.area).toLocaleString("pt-BR")} mÂ²`
                      : "NÃ£o informado"}
                  </strong>
                </div>

                <div>
                  <span>Quartos</span>
                  <strong>
                    {imovelDetalhes.quartos ?? "NÃ£o informado"}
                  </strong>
                </div>

                <div>
                  <span>Banheiros</span>
                  <strong>
                    {imovelDetalhes.banheiros ?? "NÃ£o informado"}
                  </strong>
                </div>

                <div>
                  <span>Vagas</span>
                  <strong>
                    {imovelDetalhes.vagas ?? "NÃ£o informado"}
                  </strong>
                </div>

                <div className="details-auction-wide">
                  <span>Leiloeiro</span>
                  <strong>
                    {imovelDetalhes.leiloeiro || "NÃ£o informado"}
                  </strong>
                </div>

                <div className="details-auction-wide">
                  <span>Processo</span>
                  <strong>
                    {imovelDetalhes.processo || "NÃ£o informado"}
                  </strong>
                </div>

                <div className="details-auction-wide">
                  <span>EndereÃ§o</span>
                  <strong>
                    {[
                      imovelDetalhes.endereco,
                      imovelDetalhes.cidade,
                      imovelDetalhes.estado,
                    ]
                      .filter(Boolean)
                      .join(" - ") || "NÃ£o informado"}
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
                    ðŸ”— Ver edital <ExternalLink size={17} />
                  </a>
                )}
                {imovelDetalhes.url && (
                  <a
                    href={imovelDetalhes.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="details-button"
                  >
                    ðŸ”— Ver anÃºncio original <ExternalLink size={17} />
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
