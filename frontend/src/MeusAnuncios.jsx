// "Meus anúncios": qualquer conta publica imóveis. Cada anúncio passa por aprovação
// de um administrador e exige aceitar a comissão de 6% do site sobre o valor de venda.
import { useCallback, useEffect, useState } from "react";
import { Megaphone, Pencil, Trash2 } from "lucide-react";

import { pedirApi } from "./api";
import { dinheiro } from "./imovel/analise";
import { COMISSAO_SITE } from "./legal/dados";

const VAZIO = {
  titulo: "", tipo: "", cidade: "", estado: "", endereco: "",
  valor_mercado: "", valor_anunciado: "", area: "", quartos: "", banheiros: "", vagas: "",
  descricao: "", foto: "", aceito_comissao: false,
};

const ESTADOS = {
  em_analise: { texto: "Em análise", classe: "analise" },
  publicado: { texto: "Publicado", classe: "publicado" },
  rejeitado: { texto: "Rejeitado", classe: "rejeitado" },
};

function paraCorpo(form) {
  const numero = (v) => (v === "" || v == null ? null : Number(v));
  return {
    titulo: form.titulo.trim(),
    tipo: form.tipo || null,
    cidade: form.cidade || null,
    estado: form.estado ? form.estado.trim().toUpperCase().slice(0, 2) : null,
    endereco: form.endereco || null,
    valor_mercado: Number(form.valor_mercado),
    valor_anunciado: Number(form.valor_anunciado),
    area: numero(form.area),
    quartos: numero(form.quartos),
    banheiros: numero(form.banheiros),
    vagas: numero(form.vagas),
    descricao: form.descricao || null,
    aceito_comissao: form.aceito_comissao,
  };
}

export default function MeusAnuncios({ token }) {
  const [anuncios, setAnuncios] = useState([]);
  const [form, setForm] = useState(VAZIO);
  const [editandoId, setEditandoId] = useState(null);
  const [aberto, setAberto] = useState(false);
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [guardando, setGuardando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setAnuncios(await pedirApi("/anuncios-imoveis/meus", { token }));
    } catch (falha) {
      setErro(falha.message || "Não foi possível carregar os seus anúncios.");
    }
  }, [token]);

  useEffect(() => { carregar(); }, [carregar]);

  const mudar = (campo) => (e) =>
    setForm({ ...form, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const desconto = Number(form.valor_mercado) > 0 && Number(form.valor_anunciado) > 0
    ? ((Number(form.valor_mercado) - Number(form.valor_anunciado)) / Number(form.valor_mercado)) * 100
    : null;

  function novo() {
    setForm(VAZIO);
    setEditandoId(null);
    setErro("");
    setMensagem("");
    setAberto(true);
  }

  function editar(a) {
    setForm({
      ...VAZIO,
      ...Object.fromEntries(Object.keys(VAZIO).map((k) => [k, a[k] ?? VAZIO[k]])),
      foto: "",
      aceito_comissao: true,
    });
    setEditandoId(a.id);
    setErro("");
    setMensagem("");
    setAberto(true);
  }

  async function guardar(e) {
    e.preventDefault();
    setErro("");
    setMensagem("");
    if (!form.aceito_comissao) {
      setErro(`Para publicar é preciso aceitar a comissão de ${COMISSAO_SITE}% do site.`);
      return;
    }
    setGuardando(true);
    try {
      const anuncio = await pedirApi(editandoId ? `/anuncios-imoveis/${editandoId}` : "/anuncios-imoveis", {
        metodo: editandoId ? "PUT" : "POST",
        corpo: paraCorpo(form),
        token,
        erroPadrao: "Não foi possível salvar o anúncio.",
      });
      if (form.foto.trim()) {
        await pedirApi(`/anuncios-imoveis/${anuncio.id}/fotos`, {
          metodo: "POST",
          corpo: { url: form.foto.trim(), ordem: anuncio.fotos?.length || 0 },
          token,
          erroPadrao: "O anúncio foi salvo, mas a foto não: use um endereço que comece com https://",
        });
      }
      setMensagem(anuncio.status === "publicado"
        ? "Anúncio publicado."
        : "Anúncio enviado. Fica em análise até um administrador aprovar.");
      setAberto(false);
      setForm(VAZIO);
      setEditandoId(null);
      await carregar();
    } catch (falha) {
      setErro(falha instanceof TypeError ? "Não foi possível conectar à API." : falha.message);
    } finally {
      setGuardando(false);
    }
  }

  async function apagar(a) {
    if (!window.confirm(`Apagar o anúncio "${a.titulo}"?`)) return;
    try {
      await pedirApi(`/anuncios-imoveis/${a.id}`, { metodo: "DELETE", token });
      await carregar();
    } catch (falha) {
      setErro(falha.message || "Não foi possível apagar o anúncio.");
    }
  }

  return (
    <section id="meus-anuncios" className="container meus-anuncios">
      <div className="meus-anuncios-cabecalho">
        <div>
          <span className="section-kicker">ANUNCIAR</span>
          <h2><Megaphone size={22} aria-hidden="true" /> Meus anúncios</h2>
          <p>Anuncie um imóvel seu. Cada anúncio é revisado por um administrador antes de aparecer no site.</p>
        </div>
        {!aberto && <button type="button" className="meus-anuncios-novo" onClick={novo}>Anunciar imóvel</button>}
      </div>

      {erro && <p className="alertas-erro" role="alert">{erro}</p>}
      {mensagem && <p className="meus-anuncios-ok" role="status">{mensagem}</p>}

      {aberto && (
        <form className="meus-anuncios-form" onSubmit={guardar}>
          <label className="largo">Título<input required maxLength="255" value={form.titulo} onChange={mudar("titulo")} placeholder="Ex.: Apartamento 2 quartos no centro" /></label>
          <label>Tipo<input maxLength="100" value={form.tipo} onChange={mudar("tipo")} placeholder="Casa, apartamento..." /></label>
          <label>Cidade<input maxLength="100" value={form.cidade} onChange={mudar("cidade")} /></label>
          <label>Estado (UF)<input maxLength="2" value={form.estado} onChange={mudar("estado")} placeholder="SP" /></label>
          <label className="largo">Endereço<input maxLength="255" value={form.endereco} onChange={mudar("endereco")} /></label>
          <label>Valor de mercado (R$)<input required type="number" min="1" step="0.01" value={form.valor_mercado} onChange={mudar("valor_mercado")} /></label>
          <label>Valor pedido (R$)<input required type="number" min="1" step="0.01" value={form.valor_anunciado} onChange={mudar("valor_anunciado")} /></label>
          <label>Área (m²)<input type="number" min="0" step="0.01" value={form.area} onChange={mudar("area")} /></label>
          <label>Quartos<input type="number" min="0" value={form.quartos} onChange={mudar("quartos")} /></label>
          <label>Banheiros<input type="number" min="0" value={form.banheiros} onChange={mudar("banheiros")} /></label>
          <label>Vagas<input type="number" min="0" value={form.vagas} onChange={mudar("vagas")} /></label>
          <label className="largo">Descrição<textarea rows="3" value={form.descricao} onChange={mudar("descricao")} /></label>
          <label className="largo">Foto (endereço da imagem, opcional)<input value={form.foto} onChange={mudar("foto")} placeholder="https://..." /></label>

          {desconto !== null && (
            <p className="largo meus-anuncios-resumo">
              {desconto > 0 ? `${desconto.toFixed(1).replace(".", ",")}% abaixo do valor de mercado.` : "Sem desconto sobre o valor de mercado."}
              {" "}Comissão do site se vender pelo Radar Leilão: {dinheiro((Number(form.valor_anunciado) * COMISSAO_SITE) / 100)} ({COMISSAO_SITE}% do valor pedido; calculada sobre o valor final de venda).
            </p>
          )}

          <label className="largo meus-anuncios-comissao">
            <input type="checkbox" checked={form.aceito_comissao} onChange={mudar("aceito_comissao")} />
            <span>
              Aceito pagar ao Radar Leilão uma comissão de {COMISSAO_SITE}% sobre o valor de venda, se o negócio
              fechar pelo site, conforme os <a href="/termos" target="_blank" rel="noopener">Termos de Uso</a>.
            </span>
          </label>

          <div className="largo meus-anuncios-botoes">
            <button type="submit" disabled={guardando}>{guardando ? "Enviando..." : editandoId ? "Salvar alterações" : "Enviar para aprovação"}</button>
            <button type="button" className="meus-anuncios-cancelar" onClick={() => { setAberto(false); setEditandoId(null); }}>Cancelar</button>
          </div>
        </form>
      )}

      {anuncios.length > 0 ? (
        <ul className="meus-anuncios-lista">
          {anuncios.map((a) => {
            const estado = ESTADOS[a.status] || { texto: a.status, classe: "" };
            return (
              <li key={a.id}>
                <div>
                  <strong>{a.titulo}</strong>
                  <span className={`meus-anuncios-estado ${estado.classe}`}>{estado.texto}</span>
                  <small>
                    {[a.cidade, a.estado].filter(Boolean).join(" - ")}
                    {a.cidade || a.estado ? " · " : ""}{dinheiro(a.valor_anunciado)}
                  </small>
                  {a.status === "rejeitado" && a.motivo_rejeicao && (
                    <small className="meus-anuncios-motivo">Motivo: {a.motivo_rejeicao}. Corrija e salve para enviar de novo.</small>
                  )}
                </div>
                <div className="meus-anuncios-acoes">
                  <button type="button" onClick={() => editar(a)} aria-label={`Editar ${a.titulo}`}><Pencil size={16} /></button>
                  <button type="button" onClick={() => apagar(a)} aria-label={`Apagar ${a.titulo}`}><Trash2 size={16} /></button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        !aberto && <p className="meus-anuncios-vazio">Ainda não tem anúncios.</p>
      )}
    </section>
  );
}
