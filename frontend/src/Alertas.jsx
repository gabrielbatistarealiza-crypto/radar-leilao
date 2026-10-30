import { useCallback, useEffect, useState } from "react";
import { Bell, Trash2, CalendarClock, MapPin, Pencil, X } from "lucide-react";

import { API_URL } from "./api";

function moeda(valor) {
  if (valor == null) return "Preço não informado";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(valor);
}

export default function Alertas({ token }) {
  const [criterios, setCriterios] = useState([]);
  const [cenarios, setCenarios] = useState([]);
  const [correspondencias, setCorrespondencias] = useState([]);
  const [notificacoes, setNotificacoes] = useState([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [editandoId, setEditandoId] = useState(null);
  const [form, setForm] = useState({ nome: "", desconto_minimo: "", preco_maximo: "", estado: "", cidade: "", roi_minimo: "", simulacao_id: "", alertar_prazos_dias: "7" });

  const requisicao = useCallback(async (rota, opcoes = {}) => {
    const resposta = await fetch(`${API_URL}${rota}`, {
      ...opcoes,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...opcoes.headers },
    });
    if (!resposta.ok) {
      const dados = await resposta.json().catch(() => ({}));
      throw new Error(dados.detail || "Não foi possível concluir a operação.");
    }
    return resposta.status === 204 ? null : resposta.json();
  }, [token]);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const [lista, opcoes, resultados, historico] = await Promise.all([
        requisicao("/alertas"), requisicao("/alertas/cenarios"), requisicao("/alertas/correspondencias"), requisicao("/alertas/notificacoes"),
      ]);
      setCriterios(lista);
      setCenarios(opcoes);
      setCorrespondencias(resultados);
      setNotificacoes(historico);
    } catch (error) {
      setErro(error.message);
    } finally {
      setCarregando(false);
    }
  }, [requisicao]);

  useEffect(() => { carregar(); }, [carregar]);

  async function salvar(event) {
    event.preventDefault();
    setSalvando(true);
    setErro("");
    const dados = Object.fromEntries(Object.entries(form).filter(([, valor]) => valor !== ""));
    for (const campo of ["desconto_minimo", "preco_maximo", "roi_minimo", "alertar_prazos_dias", "simulacao_id"]) {
      if (dados[campo] !== undefined) dados[campo] = Number(dados[campo]);
    }
    try {
      await requisicao(editandoId ? `/alertas/${editandoId}` : "/alertas", { method: editandoId ? "PUT" : "POST", body: JSON.stringify(dados) });
      setForm({ nome: "", desconto_minimo: "", preco_maximo: "", estado: "", cidade: "", roi_minimo: "", simulacao_id: "", alertar_prazos_dias: "7" });
      setEditandoId(null);
      await carregar();
    } catch (error) {
      setErro(error.message);
    } finally {
      setSalvando(false);
    }
  }

  function editar(criterio) {
    setEditandoId(criterio.id);
    setForm({
      nome: criterio.nome ?? "", desconto_minimo: criterio.desconto_minimo ?? "",
      preco_maximo: criterio.preco_maximo ?? "", estado: criterio.estado ?? "",
      cidade: criterio.cidade ?? "", roi_minimo: criterio.roi_minimo ?? "",
      simulacao_id: criterio.simulacao_id ?? "", alertar_prazos_dias: String(criterio.alertar_prazos_dias ?? 7),
    });
    setErro("");
    document.querySelector(".alertas-form")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function cancelarEdicao() {
    setEditandoId(null);
    setForm({ nome: "", desconto_minimo: "", preco_maximo: "", estado: "", cidade: "", roi_minimo: "", simulacao_id: "", alertar_prazos_dias: "7" });
  }

  async function excluir(id) {
    try {
      await requisicao(`/alertas/${id}`, { method: "DELETE" });
      await carregar();
    } catch (error) { setErro(error.message); }
  }

  async function marcarLida(id) {
    try {
      const atualizada = await requisicao(`/alertas/notificacoes/${id}/lida`, { method: "POST" });
      setNotificacoes((atuais) => atuais.map((item) => item.id === id ? atualizada : item));
    } catch (error) { setErro(error.message); }
  }

  return (
    <section id="alertas" className="container alertas-section">
      <div className="alertas-heading">
        <div><span className="section-kicker">ACOMPANHAMENTO</span><h2><Bell size={22} /> Alertas de oportunidades</h2><p>Guarde critérios e veja imóveis atuais que combinam com eles, incluindo leilões próximos.</p></div>
      </div>
      {erro && <p className="alertas-erro" role="alert">{erro}</p>}
      <form className="alertas-form" onSubmit={salvar}>
        <label>Nome do alerta<input required maxLength="120" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex.: Apartamentos em SP" /></label>
        <label>Desconto mínimo (%)<input type="number" min="0" max="100" step="0.1" value={form.desconto_minimo} onChange={(e) => setForm({ ...form, desconto_minimo: e.target.value })} placeholder="Ex.: 30" /></label>
        <label>Preço máximo<input type="number" min="1" step="1000" value={form.preco_maximo} onChange={(e) => setForm({ ...form, preco_maximo: e.target.value })} placeholder="Ex.: 300000" /></label>
        <label>Estado<input maxLength="2" value={form.estado} onChange={(e) => setForm({ ...form, estado: e.target.value.toUpperCase() })} placeholder="SP" /></label>
        <label>Cidade<input maxLength="100" value={form.cidade} onChange={(e) => setForm({ ...form, cidade: e.target.value })} placeholder="Campinas" /></label>
        <label>Prazo do leilão<input type="number" min="0" max="90" value={form.alertar_prazos_dias} onChange={(e) => setForm({ ...form, alertar_prazos_dias: e.target.value })} /><small>Alertar quando faltar até este número de dias.</small></label>
        <label>Cenário guardado para ROI<select value={form.simulacao_id} onChange={(e) => setForm({ ...form, simulacao_id: e.target.value, roi_minimo: e.target.value ? form.roi_minimo : "" })}><option value="">Sem filtro de ROI</option>{cenarios.filter((c) => !c.custos_nao_informados.length).map((c) => <option key={c.id} value={c.id}>{c.nome} · imóvel #{c.imovel_id}</option>)}</select><small>Somente cenários com custos completos.{cenarios.some((c) => c.custos_nao_informados.length > 0) ? " Os cenários incompletos não são usados para estimar ROI." : ""}</small></label>
        <label>ROI mínimo (%)<input type="number" min="-100" max="10000" step="0.1" disabled={!form.simulacao_id} value={form.roi_minimo} onChange={(e) => setForm({ ...form, roi_minimo: e.target.value })} placeholder="Ex.: 15" /></label>
        <button type="submit" disabled={salvando}>{salvando ? "A guardar…" : editandoId ? "Atualizar alerta" : "Guardar alerta"}</button>
        {editandoId && <button type="button" className="alerta-cancelar-edicao" onClick={cancelarEdicao}><X size={16} /> Cancelar edição</button>}
      </form>

      <div className="alertas-grid">
        <div className="alertas-panel alertas-historico"><h3>Notificações ({notificacoes.filter((item) => !item.lida).length} não lidas)</h3>
          {notificacoes.length === 0 ? <p className="alertas-vazio">Ainda não há notificações. Verificamos novos resultados e prazos automaticamente a cada 15 minutos.</p> : notificacoes.map((item) => <article className={`notificacao-item${item.lida ? " lida" : ""}`} key={item.id}><div><strong>{item.titulo}</strong><p>{item.mensagem}</p><small>{new Date(`${item.criada_em}Z`).toLocaleString("pt-BR")}</small></div>{!item.lida && <button type="button" onClick={() => marcarLida(item.id)}>Marcar como lida</button>}</article>)}
        </div>
        <div className="alertas-panel"><h3>Critérios guardados ({criterios.length})</h3>
          {criterios.length === 0 ? <p className="alertas-vazio">Ainda não há critérios guardados.</p> : criterios.map((c) => <article className="alerta-criterio" key={c.id}><div><strong>{c.nome}</strong><p>{[c.desconto_minimo != null && `Desconto ≥ ${c.desconto_minimo}%`, c.preco_maximo != null && `Preço ≤ ${moeda(c.preco_maximo)}`, c.estado, c.cidade, c.roi_minimo != null && `ROI ≥ ${c.roi_minimo}%`, `Leilões em até ${c.alertar_prazos_dias} dias`].filter(Boolean).join(" · ")}</p></div><div className="alerta-acoes"><button type="button" className="alerta-editar" aria-label={`Editar alerta ${c.nome}`} onClick={() => editar(c)}><Pencil size={16} /></button><button type="button" className="alerta-excluir" aria-label={`Excluir alerta ${c.nome}`} onClick={() => excluir(c.id)}><Trash2 size={16} /></button></div></article>)}
        </div>
        <div className="alertas-panel"><h3>Imóveis relevantes ({correspondencias.length})</h3>
          {carregando ? <p className="alertas-vazio">A procurar correspondências…</p> : correspondencias.length === 0 ? <p className="alertas-vazio">Sem correspondências por agora. Os critérios guardados serão comparados com o catálogo atual.</p> : correspondencias.map((item, index) => <article className="alerta-imovel" key={`${item.criterio_id}-${item.imovel.id}-${index}`}><div className="alerta-imovel-titulo"><strong>{item.imovel.titulo}</strong><span>{moeda(item.imovel.valor_leilao)}</span></div><p><MapPin size={14} /> {[item.imovel.cidade, item.imovel.estado].filter(Boolean).join(" · ")} · {item.criterio_nome}</p><ul>{item.motivos.map((motivo, i) => <li key={i}>{motivo}</li>)}</ul>{item.pendencia_custos && <p className="alertas-pendencia">Custos a completar: {item.pendencia_custos}</p>}{item.alerta_prazo && <p className="alertas-prazo"><CalendarClock size={15} /> Prazo de leilão próximo</p>}{item.imovel.url && <a href={item.imovel.url} target="_blank" rel="noreferrer">Abrir anúncio</a>}</article>)}
        </div>
      </div>
    </section>
  );
}
