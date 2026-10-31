import { useCallback, useEffect, useRef, useState } from "react";
import { Route, Routes, useLocation, useNavigate } from "react-router-dom";
import Login from "./Login";
import { RedefinirSenha } from "./RecuperarSenha";
import DesligarAlertas from "./DesligarAlertas";
import Admin from "./Admin";
import MinhasOportunidades from "./MinhasOportunidades";
import Corretor from "./Corretor";
import StatusCaixa from "./StatusCaixa";
import Alertas from "./Alertas";
import Consultoria from "./Consultoria";
import {
  SlidersHorizontal,
  X,
  ArrowDownUp,
  Building2,
  AlertTriangle,
} from "lucide-react";

import "./App.css";
import {
  analiseFinanceira,
  analiseDoCenario,
  calcularScoreOportunidade,
  decisaoDaOportunidade,
  detalhesDoScore,
  fotosDoImovel,
} from "./imovel/analise";

import { API_URL } from "./api";
import DetalhesImovel from "./componentes/DetalhesImovel";
import CartaoImovel from "./componentes/CartaoImovel";
import GaleriaFotos from "./componentes/GaleriaFotos";
import Paginacao from "./componentes/Paginacao";
import PainelComparacao from "./componentes/PainelComparacao";
import Cabecalho from "./componentes/Cabecalho";
import PerfilCliente from "./componentes/PerfilCliente";
import PerfilCorretor from "./componentes/PerfilCorretor";
import TopoPesquisa from "./componentes/TopoPesquisa";
import { papelDoUsuario } from "./papel";

function App() {
  const location = useLocation();
  const navegar = useNavigate();
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

    if (location.pathname === "/admin") {
      navegar("/", { replace: true });
    }
  }

  useEffect(() => {
    localStorage.setItem(
      "radar-leilao-favoritos",
      JSON.stringify(favoritos)
    );
  }, [favoritos]);
 

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

  // A ligação do e-mail de recuperação abre esta página com ou sem sessão.
  if (location.pathname === "/redefinir-senha") {
    return (
      <RedefinirSenha
        codigo={new URLSearchParams(location.search).get("codigo") || ""}
        onConcluido={() => navegar("/", { replace: true })}
      />
    );
  }

  // A ligação "deixar de receber" do resumo de alertas também abre sem sessão.
  if (location.pathname === "/desligar-alertas") {
    return (
      <DesligarAlertas
        token={new URLSearchParams(location.search).get("token") || ""}
        onConcluido={() => navegar("/", { replace: true })}
      />
    );
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

  const acessoNegado = (
    <div className="login-page">
      <div className="login-card">
        <h1>Radar Leilão</h1>
        <p>Acesso permitido apenas para administradores.</p>

        <button type="button" onClick={() => navegar("/")}>
          Voltar
        </button>
      </div>
    </div>
  );

  const paginaPrincipal = (
    <div
            
    className="app">

            {/* HEADER */}
        <Cabecalho
          ehAdministrador={ehAdministrador}
          papel={papel}
          sair={sair}
        />

        {(papel === "cliente" || papel === "corretor" || papel === "admin") && <Alertas token={token} />}

        {papel === "cliente" && (
          <>
            <PerfilCliente
              token={token}
              usuario={usuario}
            />

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
            <PerfilCorretor
              usuario={usuario}
            />
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
      <TopoPesquisa
        busca={busca}
        pesquisar={pesquisar}
        setBusca={setBusca}
      />

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
              <PainelComparacao
                alternarComparacao={alternarComparacao}
                dadosComparacao={dadosComparacao}
                imoveisComparacao={imoveisComparacao}
                setImoveisComparacao={setImoveisComparacao}
              />
            )}

            <div className="imoveis-grid">

              {listaRenderizadaRadar.map((imovel) => {
                return (
                  <CartaoImovel
                    key={imovel.id}
                    abrirDetalhes={abrirDetalhes}
                    abrirGaleria={abrirGaleria}
                    alternarComparacao={alternarComparacao}
                    alternarFavorito={alternarFavorito}
                    favoritos={favoritos}
                    imoveisComparacao={imoveisComparacao}
                    imovel={imovel}
                    papel={papel}
                  />
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

            <Paginacao
              mudarPagina={mudarPagina}
              pagina={pagina}
              paginas={paginas}
              paginasVisiveis={paginasVisiveis}
            />

          )}

      </main>

      {(papel === "cliente" || papel === "corretor") && (
        <Consultoria token={token} />
      )}

      {/* GALERIA */}
      {galeriaAberta && (
        <GaleriaFotos
          fotoAnterior={fotoAnterior}
          fotoAtiva={fotoAtiva}
          galeriaAberta={galeriaAberta}
          proximaFoto={proximaFoto}
          setFotoAtiva={setFotoAtiva}
          setGaleriaAberta={setGaleriaAberta}
        />
      )}

      {/* DETALHES DO IMÓVEL */}
      {imovelDetalhes && (
        <DetalhesImovel
          IconeDecisao={IconeDecisao}
          abrirGaleria={abrirGaleria}
          alternarFavorito={alternarFavorito}
          analiseDetalhes={analiseDetalhes}
          atualizarCenarioSelecionado={atualizarCenarioSelecionado}
          atualizarCustoArremate={atualizarCustoArremate}
          cenarioDetalhes={cenarioDetalhes}
          custosArremate={custosArremate}
          decisaoDetalhes={decisaoDetalhes}
          favoritos={favoritos}
          fotoDetalhesAtiva={fotoDetalhesAtiva}
          imovelDetalhes={imovelDetalhes}
          oportunidadeDetalhes={oportunidadeDetalhes}
          oportunidadeSelecionada={oportunidadeSelecionada}
          papel={papel}
          scoreDetalhes={scoreDetalhes}
          setFotoDetalhesAtiva={setFotoDetalhesAtiva}
          setImovelDetalhes={setImovelDetalhes}
          token={token}
          usuario={usuario}
        />
      )}
    </div>
  );

  return (
    <Routes>
      <Route
        path="/admin"
        element={ehAdministrador ? <Admin usuario={usuario} onLogout={sair} /> : acessoNegado}
      />
      <Route path="*" element={paginaPrincipal} />
    </Routes>
  );
}

export default App;
