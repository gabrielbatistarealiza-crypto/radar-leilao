import { useEffect, useMemo, useRef, useState } from "react";
import { Scale, SendHorizontal, LoaderCircle } from "lucide-react";
import "./Consultoria.css";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const LIMITE_PERGUNTA = 1500;

const AVISO_PADRAO =
  "Orientação informativa e geral. Não substitui a leitura do edital nem a análise do advogado da nossa equipe.";

const PERGUNTAS_GERAIS = [
  "Qual a diferença entre leilão judicial e extrajudicial?",
  "Quais custos existem além do valor do lance?",
  "Quais são os principais riscos de arrematar um imóvel?",
];

export function perguntasSugeridas(imovel) {
  if (!imovel) return PERGUNTAS_GERAIS;

  const sugestoes = [];

  if (imovel.ocupado === true) {
    sugestoes.push("Este imóvel está ocupado. Como funciona a desocupação?");
  }
  if (imovel.aceita_financiamento === true || imovel.aceita_fgts === true) {
    sugestoes.push("Posso usar financiamento ou FGTS neste leilão?");
  }
  if (imovel.modalidade) {
    sugestoes.push(`O que muda numa arrematação na modalidade "${imovel.modalidade}"?`);
  }
  sugestoes.push("Que pontos do edital devo conferir antes de dar o lance?");
  sugestoes.push("Quais custos devo prever além do lance?");

  return sugestoes.slice(0, 4);
}

export default function Consultoria({ token, imovel = null }) {
  const [mensagens, setMensagens] = useState([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState(AVISO_PADRAO);
  const fimRef = useRef(null);

  const sugestoes = useMemo(() => perguntasSugeridas(imovel), [imovel]);
  const imovelId = imovel?.id ?? null;

  // Trocar de imóvel começa uma conversa nova, para não misturar contextos.
  useEffect(() => {
    setMensagens([]);
    setErro("");
    setTexto("");
  }, [imovelId]);

  useEffect(() => {
    fimRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [mensagens, enviando]);

  async function perguntar(pergunta) {
    const limpa = pergunta.trim();
    if (!limpa || enviando) return;

    const historico = mensagens.map(({ role, content }) => ({ role, content }));

    setMensagens((atuais) => [...atuais, { role: "user", content: limpa }]);
    setTexto("");
    setErro("");
    setEnviando(true);

    try {
      const resposta = await fetch(`${API_URL}/consultoria/perguntar`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          pergunta: limpa,
          historico,
        }),
      });

      const dados = await resposta.json().catch(() => null);

      if (!resposta.ok) {
        throw new Error(
          dados?.detail || "Não foi possível obter a resposta da consultoria."
        );
      }

      if (dados?.aviso) setAviso(dados.aviso);
      setMensagens((atuais) => [
        ...atuais,
        {
          role: "assistant",
          content: dados?.resposta || "",
        },
      ]);
    } catch (error) {
      setErro(error.message || "Não foi possível obter a resposta da consultoria.");
    } finally {
      setEnviando(false);
    }
  }

  function aoEnviar(event) {
    event.preventDefault();
    perguntar(texto);
  }

  function aoTeclar(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      perguntar(texto);
    }
  }

  return (
    <section id="consultoria" className="consultoria container">
      <header className="consultoria-cabecalho">
        <h2>
          <Scale size={22} aria-hidden="true" /> Dúvidas sobre leilão
        </h2>
        <p>
          {imovel
            ? `Pergunte sobre este imóvel${imovel.titulo ? `: ${imovel.titulo}` : ""}.`
            : "Tire dúvidas sobre como funciona a compra de imóveis em leilão."}
        </p>
      </header>

      <p className="consultoria-aviso" role="note">
        {aviso}
      </p>

      <div
        className="consultoria-conversa"
        role="log"
        aria-live="polite"
        aria-label="Conversa com a consultoria"
      >
        {mensagens.length === 0 && (
          <div className="consultoria-vazio">
            <p>Comece por uma destas perguntas ou escreva a sua:</p>
            <div className="consultoria-sugestoes">
              {sugestoes.map((sugestao) => (
                <button
                  type="button"
                  key={sugestao}
                  onClick={() => perguntar(sugestao)}
                  disabled={enviando}
                >
                  {sugestao}
                </button>
              ))}
            </div>
          </div>
        )}

        {mensagens.map((mensagem, indice) => (
          <div
            key={indice}
            className={`consultoria-mensagem ${
              mensagem.role === "user" ? "do-usuario" : "do-assistente"
            }`}
          >
            <span className="consultoria-autor">
              {mensagem.role === "user" ? "Você" : "Consultoria"}
            </span>
            <p>{mensagem.content}</p>
          </div>
        ))}

        {enviando && (
          <div className="consultoria-mensagem do-assistente" aria-busy="true">
            <span className="consultoria-autor">Consultoria</span>
            <p className="consultoria-digitando">
              <LoaderCircle size={16} className="spin" aria-hidden="true" />
              Preparando a resposta...
            </p>
          </div>
        )}

        <div ref={fimRef} />
      </div>

      {erro && (
        <div className="consultoria-erro" role="alert">
          {erro}
        </div>
      )}

      <form className="consultoria-form" onSubmit={aoEnviar}>
        <label htmlFor="consultoria-pergunta" className="consultoria-rotulo">
          Sua pergunta
        </label>
        <textarea
          id="consultoria-pergunta"
          rows={2}
          maxLength={LIMITE_PERGUNTA}
          value={texto}
          onChange={(event) => setTexto(event.target.value)}
          onKeyDown={aoTeclar}
          placeholder="Ex.: Quem paga as dívidas de condomínio?"
        />
        <button type="submit" disabled={enviando || !texto.trim()}>
          <SendHorizontal size={16} aria-hidden="true" />
          Enviar pergunta
        </button>
      </form>
    </section>
  );
}
