// "Imóveis anunciados": anúncios aprovados, na página principal, com "Tenho interesse".
// O interesse cria uma oportunidade: vai para o corretor do anúncio ou, se quem
// anunciou não for corretor, fica à espera de um corretor atribuído pelo administrador.
import { useEffect, useState } from "react";
import { Home, MapPin } from "lucide-react";

import { pedirApi } from "./api";
import { dinheiro } from "./imovel/analise";
import { urlDaFoto } from "./imagens";

export default function AnunciosPublicos({ usuario, token }) {
  const [anuncios, setAnuncios] = useState([]);
  const [aviso, setAviso] = useState({});
  const [aEnviar, setAEnviar] = useState(null);

  useEffect(() => {
    let ativo = true;
    pedirApi("/anuncios-imoveis/publicados", { token })
      .then((dados) => ativo && setAnuncios(Array.isArray(dados) ? dados : []))
      .catch(() => ativo && setAnuncios([]));
    return () => { ativo = false; };
  }, [token]);

  if (!anuncios.length) return null;

  async function interesse(anuncio) {
    setAEnviar(anuncio.id);
    try {
      await pedirApi(`/oportunidades/anuncio/${anuncio.id}/interesse`, {
        metodo: "POST",
        token,
        erroPadrao: "Não foi possível registrar o interesse.",
      });
      setAviso({ ...aviso, [anuncio.id]: { ok: true, texto: "Interesse registrado. Você será contatado em breve." } });
    } catch (falha) {
      setAviso({ ...aviso, [anuncio.id]: { ok: false, texto: falha.message } });
    } finally {
      setAEnviar(null);
    }
  }

  const podeInteresse = usuario?.tipo === "cliente" || usuario?.tipo === "admin" || usuario?.admin;

  return (
    <section id="imoveis-anunciados" className="container anuncios-publicos">
      <span className="section-kicker">IMÓVEIS ANUNCIADOS</span>
      <h2>Imóveis anunciados</h2>
      <p className="anuncios-publicos-sub">Imóveis anunciados por proprietários e corretores, revisados pela equipe do Radar Leilão.</p>
      <ul className="vitrine-grelha">
        {anuncios.map((a) => {
          const foto = urlDaFoto(a.fotos?.[0]?.url);
          const resultado = aviso[a.id];
          return (
            <li key={a.id}>
              <article className="vitrine-cartao anuncio-publico">
                <div className="vitrine-foto">
                  {foto ? <img src={foto} alt={a.titulo} loading="lazy" /> : <div className="vitrine-sem-foto"><Home size={28} /></div>}
                  {Math.floor(Number(a.desconto) || 0) >= 1 && <span className="vitrine-desconto">-{Math.floor(a.desconto)}%</span>}
                </div>
                <div className="vitrine-texto">
                  <strong>{a.titulo}</strong>
                  <span className="vitrine-local"><MapPin size={12} aria-hidden="true" /> {[a.cidade, a.estado].filter(Boolean).join(" - ") || "Local não informado"}</span>
                  <span className="vitrine-valor">{dinheiro(a.valor_anunciado)}</span>
                  {Number(a.valor_mercado) > Number(a.valor_anunciado) && (
                    <span className="vitrine-avaliacao">Mercado {dinheiro(a.valor_mercado)}</span>
                  )}
                  {[a.tipo, a.area ? `${a.area} m²` : null, a.quartos != null ? `${a.quartos} quartos` : null]
                    .filter(Boolean).length > 0 && (
                    <span className="vitrine-local">
                      {[a.tipo, a.area ? `${a.area} m²` : null, a.quartos != null ? `${a.quartos} quartos` : null].filter(Boolean).join(" · ")}
                    </span>
                  )}
                  {a.descricao && <span className="anuncio-publico-descricao">{a.descricao}</span>}
                  {a.e_meu ? (
                    <small className="anuncio-publico-nota">Este anúncio é seu.</small>
                  ) : podeInteresse ? (
                    <button type="button" className="anuncio-publico-interesse" onClick={() => interesse(a)}
                            disabled={aEnviar === a.id || resultado?.ok}>
                      {aEnviar === a.id ? "Enviando..." : resultado?.ok ? "Interesse registrado" : "Tenho interesse"}
                    </button>
                  ) : (
                    <small className="anuncio-publico-nota">Para demonstrar interesse, use uma conta de cliente.</small>
                  )}
                  {resultado && <small className={resultado.ok ? "anuncio-publico-ok" : "anuncio-publico-erro"} role="status">{resultado.texto}</small>}
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
