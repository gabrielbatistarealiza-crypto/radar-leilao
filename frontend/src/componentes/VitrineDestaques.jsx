// Vitrine do ecrã de entrada: imóveis em destaque (e anúncios de corretores,
// quando houver) para quem ainda não entrou. Os detalhes pedem conta.
import { useEffect, useState } from "react";
import { Home, MapPin } from "lucide-react";

import { pedirApi } from "../api";
import { dinheiro, formatarData } from "../imovel/analise";

function Foto({ url, alt }) {
  const [falhou, setFalhou] = useState(false);
  if (!url || falhou) {
    return (
      <div className="vitrine-sem-foto" aria-hidden="true">
        <Home size={28} />
      </div>
    );
  }
  return <img src={url} alt={alt} loading="lazy" onError={() => setFalhou(true)} />;
}

function percentagem(valor) {
  return `${Math.round(Number(valor) || 0)}%`;
}

export default function VitrineDestaques({ onEscolher }) {
  const [destaques, setDestaques] = useState([]);
  const [anuncios, setAnuncios] = useState([]);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let ativo = true;
    // Se a API falhar, a vitrine simplesmente não aparece: o login continua igual.
    Promise.allSettled([
      pedirApi("/imoveis/destaques?limite=6"),
      pedirApi("/anuncios-imoveis/publicados"),
    ]).then(([imoveis, publicados]) => {
      if (!ativo) return;
      setDestaques(imoveis.status === "fulfilled" && Array.isArray(imoveis.value) ? imoveis.value : []);
      setAnuncios(publicados.status === "fulfilled" && Array.isArray(publicados.value) ? publicados.value.slice(0, 3) : []);
      setCarregando(false);
    });
    return () => {
      ativo = false;
    };
  }, []);

  if (carregando || (!destaques.length && !anuncios.length)) return null;

  return (
    <section className="vitrine" aria-label="Oportunidades em destaque">
      {destaques.length > 0 && (
        <>
          <header className="vitrine-cabecalho">
            <h2>Oportunidades em destaque</h2>
            <p>Imóveis da Caixa com leilão marcado e lance mínimo abaixo da avaliação.</p>
          </header>
          <ul className="vitrine-grelha">
            {destaques.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  className="vitrine-cartao"
                  onClick={() => onEscolher?.(d)}
                  aria-label={`${d.tipo || "Imóvel"} em ${d.cidade}: ${percentagem(d.desconto)} abaixo da avaliação`}
                >
                  <div className="vitrine-foto">
                    <Foto url={d.foto} alt={`${d.tipo || "Imóvel"} em ${d.cidade}`} />
                    <span className="vitrine-desconto">-{percentagem(d.desconto)}</span>
                  </div>
                  <div className="vitrine-texto">
                    <strong>{d.tipo || "Imóvel"}</strong>
                    <span className="vitrine-local">
                      <MapPin size={12} aria-hidden="true" /> {d.cidade}
                      {d.estado ? ` - ${d.estado}` : ""}
                    </span>
                    <span className="vitrine-valor">Lance mínimo {dinheiro(d.valor_lance)}</span>
                    <span className="vitrine-avaliacao">Avaliação {dinheiro(d.valor_avaliacao)}</span>
                    {d.proximo_leilao && (
                      <span className="vitrine-data">Leilão em {formatarData(d.proximo_leilao)}</span>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {anuncios.length > 0 && (
        <>
          <header className="vitrine-cabecalho">
            <h2>Anúncios de corretores</h2>
          </header>
          <ul className="vitrine-grelha">
            {anuncios.map((a) => (
              <li key={`anuncio-${a.id}`}>
                <button type="button" className="vitrine-cartao" onClick={() => onEscolher?.(a)}>
                  <div className="vitrine-foto">
                    <Foto url={a.fotos?.[0]?.url} alt={a.titulo} />
                    {Number(a.desconto) > 0 && (
                      <span className="vitrine-desconto">-{percentagem(a.desconto)}</span>
                    )}
                  </div>
                  <div className="vitrine-texto">
                    <strong>{a.titulo}</strong>
                    <span className="vitrine-local">
                      <MapPin size={12} aria-hidden="true" /> {a.cidade}
                      {a.estado ? ` - ${a.estado}` : ""}
                    </span>
                    <span className="vitrine-valor">{dinheiro(a.valor_anunciado)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
