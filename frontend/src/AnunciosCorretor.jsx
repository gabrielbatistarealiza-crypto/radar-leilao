import { useEffect, useState } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  MapPin,
  Home,
  X,
  Image as ImageIcon,
} from "lucide-react";

import { API_URL } from "./api";

const FORM_INICIAL = {
  titulo: "",
  tipo: "",
  endereco: "",
  cidade: "",
  estado: "",
  valor_mercado: "",
  valor_anunciado: "",
  area: "",
  quartos: "",
  banheiros: "",
  vagas: "",
  descricao: "",
};

function dinheiro(valor) {
  const numero = Number(valor);

  if (!Number.isFinite(numero)) {
    return "Não informado";
  }

  return numero.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export default function AnunciosCorretor({ usuario, token }) {
  const [corretorId, setCorretorId] = useState(null);
  const [anuncios, setAnuncios] = useState([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [mensagem, setMensagem] = useState("");

  const [modalAberto, setModalAberto] = useState(false);
  const [editando, setEditando] = useState(null);
  const [form, setForm] = useState(FORM_INICIAL);
  const [salvando, setSalvando] = useState(false);
  const [fotoUrl, setFotoUrl] = useState("");
  const [adicionandoFoto, setAdicionandoFoto] = useState(false);

  async function carregarCorretor() {
    const resposta = await fetch(
      `${API_URL}/corretores/usuario/${usuario.id}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );  

    if (!resposta.ok) {
      throw new Error("Perfil de corretor não encontrado.");
    }

    const dados = await resposta.json();

    setCorretorId(dados.id);

    return dados.id;
  }

  async function carregarPainel() {
    if (!usuario?.id || !token) {
      setCarregando(false);
      return;
    }

    setCarregando(true);
    setErro("");

    try {
      const respostaCorretor = await fetch(
        `${API_URL}/corretores/usuario/${usuario.id}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const dadosCorretor = await respostaCorretor.json().catch(() => null);

      if (!respostaCorretor.ok) {
        throw new Error(
          dadosCorretor?.detail ||
            `Não foi possível carregar o perfil de corretor (${respostaCorretor.status}).`
        );
      }

      const idCorretor = dadosCorretor.id;

      setCorretorId(idCorretor);

      const respostaAnuncios = await fetch(
        `${API_URL}/anuncios-imoveis/corretor/${idCorretor}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const dadosAnuncios = await respostaAnuncios.json().catch(() => null);

      if (!respostaAnuncios.ok) {
        throw new Error(
          dadosAnuncios?.detail ||
            `Não foi possível carregar os anúncios (${respostaAnuncios.status}).`
        );
      }

      setAnuncios(
        Array.isArray(dadosAnuncios)
          ? dadosAnuncios
          : []
      );
    } catch (error) {
      console.error("Erro ao carregar anúncios do corretor:", error);

      setErro(
        error.message || "Não foi possível carregar os anúncios."
      );

      setAnuncios([]);
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregarPainel();
  }, [usuario?.id, token]);

  function abrirNovo() {
    setEditando(null);
    setForm(FORM_INICIAL);
    setMensagem("");
    setErro("");
    setModalAberto(true);
  }

  function abrirEdicao(anuncio) {
    setEditando(anuncio);
    setFotoUrl("");

    setForm({
      titulo: anuncio.titulo || "",
      tipo: anuncio.tipo || "",
      endereco: anuncio.endereco || "",
      cidade: anuncio.cidade || "",
      estado: anuncio.estado || "",
      valor_mercado: anuncio.valor_mercado ?? "",
      valor_anunciado: anuncio.valor_anunciado ?? "",
      area: anuncio.area ?? "",
      quartos: anuncio.quartos ?? "",
      banheiros: anuncio.banheiros ?? "",
      vagas: anuncio.vagas ?? "",
      descricao: anuncio.descricao || "",
      
    });

    setMensagem("");
    setErro("");
    setModalAberto(true);
  }

  function fecharModal() {
    if (salvando) {
      return;
    }

    setModalAberto(false);
    setEditando(null);
    setForm(FORM_INICIAL);
  }

  function alterarCampo(campo, valor) {
    setForm((atual) => ({
      ...atual,
      [campo]: valor,
    }));
  }

  function montarPayload() {
    return {
      corretor_id: corretorId,
      titulo: form.titulo.trim(),
      tipo: form.tipo.trim() || null,
      endereco: form.endereco.trim() || null,
      cidade: form.cidade.trim() || null,
      estado: form.estado.trim() || null,
      valor_mercado: Number(form.valor_mercado),
      valor_anunciado: Number(form.valor_anunciado),
      area: form.area === "" ? null : Number(form.area),
      quartos: form.quartos === "" ? null : Number(form.quartos),
      banheiros: form.banheiros === "" ? null : Number(form.banheiros),
      vagas: form.vagas === "" ? null : Number(form.vagas),
      descricao: form.descricao.trim() || null,
    };
  }

  async function adicionarFoto(anuncioId) {
  const url = fotoUrl.trim();

  if (!url) {
    setErro("Informe a URL da foto.");
    return;
  }

  setAdicionandoFoto(true);
  setErro("");
  setMensagem("");

  try {
    const resposta = await fetch(
      `${API_URL}/anuncios-imoveis/${anuncioId}/fotos`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          url,
          ordem: 0,
        }),
      }
    );

    const dados = await resposta.json().catch(() => null);

    if (!resposta.ok) {
      throw new Error(
        dados?.detail || "Não foi possível adicionar a foto."
      );
    }

    setFotoUrl("");
    setMensagem("Foto adicionada com sucesso.");

    await carregarPainel();
  } catch (error) {
    console.error("Erro ao adicionar foto:", error);
    setErro(error.message || "Não foi possível adicionar a foto.");
  } finally {
    setAdicionandoFoto(false);
  }
}

  async function salvarAnuncio(event) {
    event.preventDefault();

    if (!corretorId) {
      setErro("Perfil de corretor não encontrado.");
      return;
    }

    if (!form.titulo.trim()) {
      setErro("Informe o título do anúncio.");
      return;
    }

    if (
      !form.valor_mercado ||
      !form.valor_anunciado
    ) {
      setErro("Informe o valor de mercado e o valor anunciado.");
      return;
    }

    const valorMercado = Number(form.valor_mercado);
    const valorAnunciado = Number(form.valor_anunciado);

    if (valorMercado <= 0 || valorAnunciado <= 0) {
      setErro("Os valores precisam ser maiores que zero.");
      return;
    }

    if (valorAnunciado > valorMercado) {
      setErro(
        "O valor anunciado não pode ser maior que o valor de mercado."
      );
      return;
    }

    const desconto =
      ((valorMercado - valorAnunciado) / valorMercado) * 100;

    if (desconto < 20) {
      setErro(
        `O anúncio precisa ter pelo menos 20% de desconto. Atualmente: ${desconto.toFixed(
          2
        )}%.`
      );
      return;
    }

    try {
      setSalvando(true);
      setErro("");
      setMensagem("");

      const payload = montarPayload();

      let resposta;

      if (editando) {
        resposta = await fetch(
          `${API_URL}/anuncios-imoveis/${editando.id}`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(payload),
          }
        );
      } else {
        resposta = await fetch(
          `${API_URL}/anuncios-imoveis`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify(payload),
          }
        );
      }

      const dados = await resposta.json().catch(() => null);

      if (!resposta.ok) {
        throw new Error(
          dados?.detail ||
            `Erro ao salvar anúncio (${resposta.status}).`
        );
      }

      await carregarPainel();

      setMensagem(
        editando
          ? "Anúncio atualizado com sucesso."
          : "Anúncio criado com sucesso."
      );

      fecharModal();
    } catch (error) {
      console.error("Erro ao salvar anúncio:", error);
      setErro(error.message || "Não foi possível salvar o anúncio.");
    } finally {
      setSalvando(false);
    }
  }

  async function excluirAnuncio(anuncio) {
    const confirmar = window.confirm(
      `Excluir o anúncio "${anuncio.titulo}"?\n\nEssa ação não poderá ser desfeita.`
    );

    if (!confirmar) {
      return;
    }

    try {
      setErro("");
      setMensagem("");

      const resposta = await fetch(
        `${API_URL}/anuncios-imoveis/${anuncio.id}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => null);

        throw new Error(
          dados?.detail ||
            `Erro ao excluir anúncio (${resposta.status}).`
        );
      }

      setAnuncios((atuais) =>
        atuais.filter((item) => item.id !== anuncio.id)
      );

      setMensagem("Anúncio excluído com sucesso.");
    } catch (error) {
      console.error("Erro ao excluir anúncio:", error);
      setErro(error.message || "Não foi possível excluir o anúncio.");
    }
  }

  return (
    <section
      id="meus-anuncios"
      className="container corretor-anuncios-section"
    >
      <div className="corretor-anuncios-header">
        <div>
          <span className="section-kicker">
            MEUS IMÓVEIS
          </span>

          <h2>Meus anúncios</h2>

          <p>
            Gerencie os imóveis que você está anunciando no Radar Leilão.
          </p>
        </div>

        <button
          type="button"
          className="corretor-anuncio-new"
          onClick={abrirNovo}
        >
          <Plus size={18} />
          Novo anúncio
        </button>
      </div>

      {erro && (
        <div className="corretor-anuncios-alert error">
          {erro}
        </div>
      )}

      {mensagem && (
        <div className="corretor-anuncios-alert success">
          {mensagem}
        </div>
      )}

      {carregando ? (
        <div className="corretor-anuncios-carregando">
          <div className="spinner" />
          <p>Carregando seus anúncios...</p>
        </div>
      ) : anuncios.length === 0 ? (
        <div className="corretor-anuncios-empty">
          <Home size={42} />

          <h3>Você ainda não possui anúncios</h3>

          <p>
            Cadastre seu primeiro imóvel para começar a anunciar.
          </p>

          <button
            type="button"
            className="corretor-anuncio-new"
            onClick={abrirNovo}
          >
            <Plus size={18} />
            Criar primeiro anúncio
          </button>
        </div>
      ) : (
        <div className="corretor-anuncios-grid">
          {anuncios.map((anuncio) => (
            <article
              className="corretor-anuncio-card"
              key={anuncio.id}
            >
              <div className="corretor-anuncio-image">
                {anuncio.fotos?.length > 0 ? (
                  <img
                    src={anuncio.fotos[0].url}
                    alt={anuncio.titulo}
                  />
                ) : (
                  <div className="corretor-anuncio-placeholder">
                    <Home size={42} />
                    <span>Sem foto</span>
                  </div>
                )}

                <span className="corretor-anuncio-discount">
                  {Number(anuncio.desconto || 0)
                    .toFixed(2)
                    .replace(".", ",")}
                  % OFF
                </span>
              </div>

              <div className="corretor-anuncio-body">
                <h3>{anuncio.titulo}</h3>

                <div className="corretor-anuncio-location">
                  <MapPin size={15} />

                  <span>
                    {anuncio.cidade || "Cidade não informada"}
                    {anuncio.estado
                      ? ` - ${anuncio.estado}`
                      : ""}
                  </span>
                </div>

                <div className="corretor-anuncio-prices">
                  <div>
                    <span>Valor de mercado</span>
                    <strong>
                      {dinheiro(anuncio.valor_mercado)}
                    </strong>
                  </div>

                  <div>
                    <span>Valor anunciado</span>
                    <strong>
                      {dinheiro(anuncio.valor_anunciado)}
                    </strong>
                  </div>
                </div>

                <div className="corretor-anuncio-meta">
                  {anuncio.tipo && (
                    <span>{anuncio.tipo}</span>
                  )}

                  {anuncio.area && (
                    <span>{anuncio.area} m²</span>
                  )}

                  {anuncio.quartos && (
                    <span>{anuncio.quartos} quartos</span>
                  )}

                  {anuncio.vagas && (
                    <span>{anuncio.vagas} vagas</span>
                  )}
                </div>

                <div className="corretor-anuncio-actions">
                  <button
                    type="button"
                    onClick={() => abrirEdicao(anuncio)}
                  >
                    <Pencil size={16} />
                    Editar
                  </button>

                  <button
                    type="button"
                    className="danger"
                    onClick={() => excluirAnuncio(anuncio)}
                  >
                    <Trash2 size={16} />
                    Excluir
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {modalAberto && (
        <div
          className="corretor-anuncio-modal"
          onClick={fecharModal}
        >
          <div
            className="corretor-anuncio-modal-content"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="corretor-anuncio-modal-close"
              onClick={fecharModal}
              aria-label="Fechar"
            >
              <X size={22} />
            </button>

            <div className="corretor-anuncio-modal-heading">
              <span className="section-kicker">
                {editando ? "EDITAR IMÓVEL" : "NOVO IMÓVEL"}
              </span>

              <h2>
                {editando
                  ? "Editar anúncio"
                  : "Criar anúncio"}
              </h2>
            </div>

            <form onSubmit={salvarAnuncio}>
              <div className="corretor-form-grid">
                <label className="full">
                  Título *
                  <input
                    type="text"
                    value={form.titulo}
                    onChange={(event) =>
                      alterarCampo(
                        "titulo",
                        event.target.value
                      )
                    }
                    placeholder="Ex: Apartamento 3 quartos"
                    required
                  />
                </label>

                <label>
                  Tipo
                  <select
                    value={form.tipo}
                    onChange={(event) =>
                      alterarCampo(
                        "tipo",
                        event.target.value
                      )
                    }
                  >
                    <option value="">Selecione</option>
                    <option value="Casa">Casa</option>
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
                </label>

                <label>
                  Estado
                  <input
                    type="text"
                    maxLength="2"
                    value={form.estado}
                    onChange={(event) =>
                      alterarCampo(
                        "estado",
                        event.target.value.toUpperCase()
                      )
                    }
                    placeholder="PE"
                  />
                </label>

                <label>
                  Cidade
                  <input
                    type="text"
                    value={form.cidade}
                    onChange={(event) =>
                      alterarCampo(
                        "cidade",
                        event.target.value
                      )
                    }
                  />
                </label>

                <label>
                  Endereço
                  <input
                    type="text"
                    value={form.endereco}
                    onChange={(event) =>
                      alterarCampo(
                        "endereco",
                        event.target.value
                      )
                    }
                  />
                </label>

                <label>
                  Valor de mercado *
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.valor_mercado}
                    onChange={(event) =>
                      alterarCampo(
                        "valor_mercado",
                        event.target.value
                      )
                    }
                    required
                  />
                </label>

                <label>
                  Valor anunciado *
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.valor_anunciado}
                    onChange={(event) =>
                      alterarCampo(
                        "valor_anunciado",
                        event.target.value
                      )
                    }
                    required
                  />
                </label>

                <label>
                  Área (m²)
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.area}
                    onChange={(event) =>
                      alterarCampo(
                        "area",
                        event.target.value
                      )
                    }
                  />
                </label>

                <label>
                  Quartos
                  <input
                    type="number"
                    min="0"
                    value={form.quartos}
                    onChange={(event) =>
                      alterarCampo(
                        "quartos",
                        event.target.value
                      )
                    }
                  />
                </label>

                <label>
                  Banheiros
                  <input
                    type="number"
                    min="0"
                    value={form.banheiros}
                    onChange={(event) =>
                      alterarCampo(
                        "banheiros",
                        event.target.value
                      )
                    }
                  />
                </label>

                <label>
                  Vagas
                  <input
                    type="number"
                    min="0"
                    value={form.vagas}
                    onChange={(event) =>
                      alterarCampo(
                        "vagas",
                        event.target.value
                      )
                    }
                  />
                </label>

                <label className="full">
                  Descrição
                  <textarea
                    rows="5"
                    value={form.descricao}
                    onChange={(event) =>
                      alterarCampo(
                        "descricao",
                        event.target.value
                      )
                    }
                    placeholder="Descreva o imóvel..."
                  />
                </label>
              </div>

              {editando && (
                <div className="corretor-form-fotos">
                  <div className="corretor-form-fotos-title">
                    <ImageIcon size={17} />
                    <span>Fotos do imóvel</span>
                  </div>

                  <div className="corretor-form-foto-add">
                    <input
                      type="url"
                      value={fotoUrl}
                      onChange={(e) => setFotoUrl(e.target.value)}
                      placeholder="https://exemplo.com/foto.jpg"
                    />

                    <button
                      type="button"
                      className="secondary"
                      onClick={() => adicionarFoto(editando.id)}
                      disabled={adicionandoFoto || !fotoUrl.trim()}
                    >
                      {adicionandoFoto ? "Adicionando..." : "Adicionar foto"}
                    </button>
                  </div>

                  {editando.fotos?.length > 0 && (
                    <div className="corretor-form-fotos-grid">
                      {editando.fotos.map((foto) => (
                        <div
                          className="corretor-form-foto-item"
                          key={foto.id}
                        >
                          <img
                            src={foto.url}
                            alt={`Foto de ${editando.titulo}`}
                          />
                        </div>
                      ))}
                    </div>
                  )}

                  {(!editando.fotos || editando.fotos.length === 0) && (
                    <p className="corretor-form-fotos-empty">
                      Este anúncio ainda não possui fotos.
                    </p>
                  )}
                </div>
              )}

              <div className="corretor-form-actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={fecharModal}
                  disabled={salvando}
                >
                  Cancelar
                </button>

                <button
                  type="submit"
                  className="primary"
                  disabled={salvando}
                >
                  {salvando
                    ? "Salvando..."
                    : editando
                      ? "Salvar alterações"
                      : "Publicar anúncio"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
};