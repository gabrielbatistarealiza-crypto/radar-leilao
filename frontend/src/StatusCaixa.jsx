import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function StatusCaixa({ usuario }) {
  const ehAdministrador =
    usuario?.admin === true || usuario?.tipo === "admin";
  const [status, setStatus] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    // Não consultar o endpoint se o utilizador não for administrador.
    if (!ehAdministrador) {
      setStatus(null);
      setErro("");
      return undefined;
    }

    let ativo = true;

    const carregarStatus = async () => {
      const token = localStorage.getItem("radar-leilao-token");

      if (!token) {
        return;
      }

      try {
        const resposta = await fetch(`${API_URL}/caixa/status`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        const dados = await resposta.json();

        if (!resposta.ok) {
          throw new Error(
            dados.detail || "Não foi possível carregar o status da Caixa."
          );
        }

        if (ativo) {
          setStatus(dados);
          setErro("");
        }
      } catch (error) {
        if (ativo) {
          setErro(error.message || "Não foi possível carregar o status da Caixa.");
        }
      }
    };

    carregarStatus();
    const intervalo = setInterval(carregarStatus, 60000);

    return () => {
      ativo = false;
      clearInterval(intervalo);
    };
  }, [ehAdministrador]);

  // O componente também não apresenta dados para utilizadores não admin.
  if (!ehAdministrador || erro || !status) {
    return null;
  }

  const caixa = status.caixa;
  const historico = status.historico || [];

  const data = (valor) => {
    if (!valor) {
      return "—";
    }

    return new Date(valor).toLocaleString("pt-PT");
  };

  const concluida = caixa.status === "CONCLUIDA";
  const executando = caixa.status === "EXECUTANDO";
  const erroCaixa = caixa.status === "ERRO";

  const classeStatus = concluida
    ? "sucesso"
    : executando
      ? "executando"
      : erroCaixa
        ? "erro"
        : "neutro";

  const textoStatus = concluida
    ? "Concluída"
    : executando
      ? "Em execução"
      : erroCaixa
        ? "Erro"
        : "Sem execução";

  return (
    <section className="status-caixa">
      <div className="status-caixa-header">
        <div>
          <span className="status-caixa-label">MONITORAMENTO</span>
          <h3>Status da Caixa</h3>
        </div>

        <span className={`status-caixa-badge ${classeStatus}`}>
          {textoStatus}
        </span>
      </div>

      <div className="status-caixa-grid">
        <div className="status-caixa-item">
          <span>Última execução</span>
          <strong>{data(caixa.concluida_em)}</strong>
        </div>
        <div className="status-caixa-item">
          <span>Estados baixados</span>
          <strong>{caixa.estados_baixados}/27</strong>
        </div>
        <div className="status-caixa-item">
          <span>Imóveis processados</span>
          <strong>{caixa.imoveis_atualizados}</strong>
        </div>
        <div className="status-caixa-item">
          <span>Saíram da lista</span>
          <strong>{caixa.imoveis_removidos}</strong>
        </div>
        <div className="status-caixa-item">
          <span>Fotos pendentes</span>
          <strong>{caixa.fotos_pendentes}</strong>
        </div>
        <div className="status-caixa-item">
          <span>Banco</span>
          <strong>{status.banco}</strong>
        </div>
      </div>

      {caixa.erro && (
        <div className="status-caixa-erro">{caixa.erro}</div>
      )}

      <div className="status-caixa-historico">
        <div className="status-caixa-historico-header">
          <div>
            <span className="status-caixa-label">HISTÓRICO</span>
            <h4>Últimas atualizações</h4>
          </div>
          <span className="status-caixa-historico-count">
            {historico.length} registro{historico.length === 1 ? "" : "s"}
          </span>
        </div>

        {historico.length === 0 ? (
          <div className="status-caixa-sem-historico">
            Nenhuma atualização registrada.
          </div>
        ) : (
          <div className="status-caixa-tabela-wrapper">
            <table className="status-caixa-tabela">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Status</th>
                  <th>Estados</th>
                  <th>Processados</th>
                  <th>Saíram da lista</th>
                  <th>Fotos pendentes</th>
                </tr>
              </thead>
              <tbody>
                {historico.map((item) => {
                  const statusHistorico =
                    item.status === "CONCLUIDA"
                      ? "sucesso"
                      : item.status === "EXECUTANDO"
                        ? "executando"
                        : item.status === "ERRO"
                          ? "erro"
                          : "neutro";

                  const textoHistorico =
                    item.status === "CONCLUIDA"
                      ? "Concluída"
                      : item.status === "EXECUTANDO"
                        ? "Em execução"
                        : item.status === "ERRO"
                          ? "Erro"
                          : item.status;

                  return (
                    <tr key={item.id}>
                      <td>{data(item.concluida_em || item.iniciada_em)}</td>
                      <td>
                        <span
                          className={`status-caixa-mini-badge ${statusHistorico}`}
                        >
                          {textoHistorico}
                        </span>
                      </td>
                      <td>{item.estados_baixados}/27</td>
                      <td>{item.imoveis_atualizados}</td>
                      <td>{item.imoveis_removidos}</td>
                      <td>{item.fotos_pendentes}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

export default StatusCaixa;
