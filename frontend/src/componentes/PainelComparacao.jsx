// Extraído do App.jsx na fase 5 (sem alterações de comportamento).
import { calcularDesconto, dinheiro } from "../imovel/analise";

export default function PainelComparacao({
  alternarComparacao,
  dadosComparacao,
  imoveisComparacao,
  setImoveisComparacao,
}) {
  return (
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
  );
}
