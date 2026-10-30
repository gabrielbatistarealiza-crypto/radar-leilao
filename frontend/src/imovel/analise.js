// Lógica pura dos imóveis (formatação, análise financeira, score, decisão, alertas e fotos).
// Saiu do App.jsx na fase 5; não depende do estado do ecrã.
import { AlertTriangle, CircleCheck, CircleX } from "lucide-react";

// =========================================================
// FORMATAÇÃO
// =========================================================

export function dinheiro(valor) {
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

export function formatarData(data) {
  if (!data) return "Não informada";

  const valor = new Date(`${data}T00:00:00`);

  return Number.isNaN(valor.getTime())
    ? "Não informada"
    : valor.toLocaleDateString("pt-BR");
}

export function dataCivil(data) {
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

export function analiseFinanceira(imovel, custosPersonalizados = {}) {
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

export function analiseDoCenario(imovel, cenario) {
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

export function calcularDesconto(imovel) {
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

export function calcularEconomia(imovel) {
  const avaliacao = Number(imovel.valor_avaliacao || 0);
  const leilao = Number(imovel.valor_leilao || 0);

  if (!avaliacao || !leilao) {
    return 0;
  }

  return Math.max(0, avaliacao - leilao);
}

export function calcularScoreOportunidade(imovel, custosPersonalizados = {}, cenarioSelecionado = null) {
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

export function decisaoDaOportunidade(imovel, custosPersonalizados = {}, cenarioSelecionado = null) {
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

export function prioridadeDoImovel(imovel) {
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

export function alertasDoImovel(imovel) {
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

export function detalhesDoScore(imovel, custosPersonalizados = {}, cenarioSelecionado = null) {
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

export function fotosDoImovel(imovel) {
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

export function valorInputFinanceiro(valor) {
  const numero = Number(valor);

  if (!Number.isFinite(numero)) {
    return "";
  }

  return numero.toFixed(2);
}
