import { useCallback, useEffect, useState } from "react";
import "./SimuladorRentabilidade.css";

import { API_URL } from "./api";
const CAMPOS = [
  ["preco_aquisicao", "Preço de aquisição", true],
  ["impostos_taxas", "Impostos e taxas"],
  ["custos_juridicos", "Custos jurídicos"],
  ["reformas", "Reformas"],
  ["outras_despesas", "Outras despesas"],
  ["valor_revenda", "Valor esperado de revenda", true],
];
const moeda = (valor) => valor == null ? "—" : new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(valor));
const percentual = (valor) => valor == null ? "—" : `${Number(valor).toFixed(2)}%`;

export default function SimuladorRentabilidade({ oportunidadeId, token, onCenarioSelecionado, cenarioSelecionadoId = null }) {
  const [cenarios, setCenarios] = useState([]);
  const [form, setForm] = useState({ nome: "", preco_aquisicao: "", impostos_taxas: "", custos_juridicos: "", reformas: "", outras_despesas: "", valor_revenda: "", observacoes: "" });
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [cenarioId, setCenarioId] = useState(cenarioSelecionadoId == null ? "" : String(cenarioSelecionadoId));
  const carregar = useCallback(async () => {
    try {
      const resposta = await fetch(`${API_URL}/oportunidades/${oportunidadeId}/simulacoes`, { headers: { Authorization: `Bearer ${token}` } });
      if (!resposta.ok) throw new Error("Não foi possível carregar os cenários.");
      setCenarios(await resposta.json());
    } catch (e) { setErro(e.message); }
  }, [oportunidadeId, token]);
  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => {
    setCenarioId(cenarioSelecionadoId == null ? "" : String(cenarioSelecionadoId));
  }, [cenarioSelecionadoId]);
  useEffect(() => {
    onCenarioSelecionado?.(cenarioId ? cenarios.find((c) => String(c.id) === cenarioId) || null : null);
  }, [cenarioId, cenarios, onCenarioSelecionado]);
  async function salvar(event) {
    event.preventDefault(); setErro(""); setSalvando(true);
    const payload = { ...form };
    for (const [campo] of CAMPOS) payload[campo] = payload[campo] === "" ? null : Number(payload[campo]);
    try {
      const resposta = await fetch(`${API_URL}/oportunidades/${oportunidadeId}/simulacoes`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) });
      const dados = await resposta.json();
      if (!resposta.ok) throw new Error(dados.detail || "Não foi possível salvar o cenário.");
      setCenarios((atuais) => [dados, ...atuais]);
      setForm({ nome: "", preco_aquisicao: "", impostos_taxas: "", custos_juridicos: "", reformas: "", outras_despesas: "", valor_revenda: "", observacoes: "" });
    } catch (e) { setErro(e.message); } finally { setSalvando(false); }
  }
  return <section className="simulador-rentabilidade">
    <div><span className="fluxo-kicker">PLANEJAMENTO</span><h4>Simulador de rentabilidade</h4><p>Estimativas por cenário; não representam garantia de retorno. Valores ausentes são tratados como zero e destacados.</p></div>
    {erro && <div className="simulador-erro" role="alert">{erro}</div>}
    <form className="simulador-form" onSubmit={salvar}>
      <label>Nome do cenário<input required maxLength="120" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex.: Reforma básica" /></label>
      <div className="simulador-campos">{CAMPOS.map(([campo, rotulo, obrigatorio]) => <label key={campo}>{rotulo}{!obrigatorio && <small>Opcional</small>}<input type="number" min="0" step="0.01" required={obrigatorio} value={form[campo]} onChange={(e) => setForm({ ...form, [campo]: e.target.value })} placeholder="R$" /></label>)}</div>
      <label>Premissas e observações<textarea maxLength="5000" rows="2" value={form.observacoes} onChange={(e) => setForm({ ...form, observacoes: e.target.value })} placeholder="Ex.: prazo, comissão de venda, vacância ou custos ainda a confirmar" /></label>
      <button className="fluxo-primary" disabled={salvando}>{salvando ? "Salvando…" : "Salvar cenário"}</button>
    </form>
    {cenarios.length ? <div className="simulador-comparacao"><h5>Cenários salvos para esta oportunidade</h5><label className="simulador-selecao">Cenário usado no score e na decisão<select value={cenarioId} onChange={(e) => setCenarioId(e.target.value)}><option value="">Usar análise padrão do imóvel</option>{cenarios.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</select></label>{cenarioId && <p>O cenário selecionado atualiza o resultado financeiro do score e a decisão exibidos nos detalhes deste imóvel.</p>}<div className="simulador-lista">{cenarios.map((c) => <article className={`simulador-cenario ${String(c.id) === cenarioId ? "selecionado" : ""}`} key={c.id}><h5>{c.nome}</h5><dl><div><dt>Custo total</dt><dd>{moeda(c.custo_total)}</dd></div><div><dt>Lucro estimado</dt><dd>{moeda(c.lucro_estimado)}</dd></div><div><dt>Margem sobre revenda</dt><dd>{percentual(c.margem_revenda)}</dd></div><div><dt>ROI</dt><dd>{percentual(c.roi)}</dd></div></dl><p>Aquisição: {moeda(c.preco_aquisicao)} · Revenda esperada: {moeda(c.valor_revenda)}</p>{c.custos_nao_informados.length > 0 && <p className="simulador-alerta">Custos não informados (valores assumidos como zero apenas na estimativa): {c.custos_nao_informados.join(", ")}. O score não considera ROI e margem até confirmar esses custos.</p>}{c.observacoes && <p>Premissas: {c.observacoes}</p>}</article>)}</div></div> : <div className="simulador-vazio">Ainda não há cenários salvos. Crie um para comparar estimativas.</div>}
  </section>;
}
