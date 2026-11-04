// Painel de administração: anúncios em análise, para aprovar ou rejeitar (com motivo).
import { useCallback, useEffect, useState } from "react";

import { pedirApi } from "./api";
import { dinheiro } from "./imovel/analise";
import { urlDaFoto } from "./imagens";

export default function ModeracaoAnuncios({ token }) {
  const [anuncios, setAnuncios] = useState([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      setAnuncios(await pedirApi("/anuncios-imoveis/moderacao", { token }));
    } catch (falha) {
      setErro(falha.message || "Não foi possível carregar os anúncios em análise.");
    } finally {
      setCarregando(false);
    }
  }, [token]);

  useEffect(() => { carregar(); }, [carregar]);

  async function decidir(anuncio, aprovar) {
    let corpo;
    if (!aprovar) {
      const motivo = window.prompt(`Motivo para rejeitar "${anuncio.titulo}" (o anunciante vai vê-lo):`);
      if (!motivo || motivo.trim().length < 3) return;
      corpo = { motivo: motivo.trim() };
    }
    try {
      await pedirApi(`/anuncios-imoveis/${anuncio.id}/${aprovar ? "aprovar" : "rejeitar"}`, { metodo: "POST", corpo, token });
      setAnuncios((atuais) => atuais.filter((a) => a.id !== anuncio.id));
    } catch (falha) {
      setErro(falha.message || "Não foi possível salvar a decisão.");
    }
  }

  return (
    <section className="admin-section moderacao-anuncios" aria-label="Anúncios em análise">
      <div className="moderacao-cabecalho">
        <div>
          <span className="section-kicker">MODERAÇÃO</span>
          <h2>Anúncios em análise</h2>
        </div>
        <button type="button" onClick={carregar}>Atualizar</button>
      </div>
      {erro && <p className="alertas-erro" role="alert">{erro}</p>}
      {!carregando && !erro && anuncios.length === 0 && <p>Nenhum anúncio à espera de aprovação.</p>}
      <ul className="moderacao-lista">
        {anuncios.map((a) => (
          <li key={a.id}>
            <div className="moderacao-dados">
              <strong>{a.titulo}</strong>
              <small>
                {[a.tipo, [a.cidade, a.estado].filter(Boolean).join(" - ")].filter(Boolean).join(" · ")}
                {" · "}pedido {dinheiro(a.valor_anunciado)} · mercado {dinheiro(a.valor_mercado)}
              </small>
              {a.dono && <small>Anunciante: {a.dono.nome} ({a.dono.email}) · {a.dono.tipo}</small>}
              <small>Comissão aceite: {a.comissao_percentual ?? "-"}%{a.comissao_aceite_em ? ` em ${new Date(a.comissao_aceite_em).toLocaleDateString("pt-BR")}` : ""}</small>
              {a.descricao && <p>{a.descricao}</p>}
              {a.fotos?.length > 0 ? (
                <div className="moderacao-fotos">
                  {a.fotos.map((f, i) => (
                    <a key={f.id} href={urlDaFoto(f.url)} target="_blank" rel="noopener noreferrer" aria-label={`Ver foto ${i + 1}`}>
                      <img src={urlDaFoto(f.url)} alt={`Foto ${i + 1} de ${a.titulo}`} loading="lazy" />
                    </a>
                  ))}
                </div>
              ) : (
                <small>Sem fotos.</small>
              )}
            </div>
            <div className="moderacao-botoes">
              <button type="button" className="moderacao-aprovar" onClick={() => decidir(a, true)}>Aprovar</button>
              <button type="button" className="moderacao-rejeitar" onClick={() => decidir(a, false)}>Rejeitar</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
