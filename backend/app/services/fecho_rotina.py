"""Fecho da rotina da Caixa: corre no computador local, no fim da tarefa agendada.

1. Aplica os PDFs da pasta Editais que ainda não foram aplicados: primeiro em ensaio;
   só grava se o edital for coerente (sem imóveis com datas futuras diferentes). Os
   outros ficam por gravar e vão no aviso, para alguém decidir.
2. Junta o resultado da importação das listas desta execução e o resumo dos editais.
3. Grava um registo em execucoes_rotina; a API envia-o por e-mail aos administradores.

Não contacta a Caixa.
"""
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.execucao_rotina import ExecucaoRotina
from app.services.caixa_datas_edital import aplicar_edital_local, link_do_ficheiro_edital, resumo_editais

SIGNIFICADO_CODIGO = {
    0: "concluída",
    2: "parou (paragem manual, bloqueio da Caixa ou outra rotina a correr)",
    3: "não correu: a VPN estava ligada",
    4: "não correu: sem ligação à base",
    5: "não correu: hora perto da geração das listas da Caixa",
}


def significado(codigo: int) -> str:
    return SIGNIFICADO_CODIGO.get(codigo, f"erro (código {codigo})")


def aplicar_editais_da_pasta(db: Session, pasta_editais) -> dict:
    """Aplica os PDFs por aplicar. Devolve {"aplicados": [...], "problemas": [...], "ignorados": [...]}."""
    resultado = {"aplicados": [], "problemas": [], "ignorados": []}
    pasta = Path(pasta_editais) if pasta_editais else None
    if pasta is None or not pasta.is_dir():
        return resultado
    for nome in resumo_editais(db, pasta).get("pdfs_por_aplicar", []):
        link = link_do_ficheiro_edital(nome)
        if not link:
            resultado["problemas"].append({"ficheiro": nome, "motivo": "NOME_SEM_NUMERO_DO_EDITAL"})
            continue
        corpo = (pasta / nome).read_bytes()
        ensaio = aplicar_edital_local(db, corpo, link, gravar=False)
        if ensaio.get("recusado") == "EDITAL_JA_PASSOU":
            resultado["ignorados"].append({"ficheiro": nome, "motivo": "EDITAL_JA_PASSOU"})
            continue
        if ensaio.get("recusado") or ensaio.get("paragem"):
            resultado["problemas"].append({
                "ficheiro": nome, "motivo": ensaio.get("recusado") or ensaio.get("paragem"),
                "imovel_incoerente": ensaio.get("imovel_incoerente"),
            })
            continue
        gravado = aplicar_edital_local(db, corpo, link, gravar=True)
        resultado["aplicados"].append({
            "ficheiro": nome,
            "datas": [gravado.get("data_primeiro_leilao"), gravado.get("data_segundo_leilao")],
            "imoveis": gravado.get("membros_na_base", 0),
            "preenchidos": gravado.get("preenchidos_pelo_edital", 0),
            "renovados": gravado.get("renovados_pelo_edital", 0),
            "valores": gravado.get("valores_de_leilao_gravados", 0),
        })
    return resultado


def _lista_desta_execucao(db: Session, iniciada_em: datetime | None) -> dict | None:
    consulta = db.query(AtualizacaoCaixa)
    if iniciada_em is not None:
        consulta = consulta.filter(AtualizacaoCaixa.iniciada_em >= iniciada_em)
    ultima = consulta.order_by(AtualizacaoCaixa.iniciada_em.desc()).first()
    if ultima is None:
        return None
    return {"status": ultima.status, "estados_baixados": ultima.estados_baixados,
            "imoveis_atualizados": ultima.imoveis_atualizados, "imoveis_removidos": ultima.imoveis_removidos,
            "erro": (ultima.erro or "")[:500] or None}


def fechar_execucao(db: Session, *, codigo_saida: int, iniciada_em: datetime | None = None,
                    pasta_editais=None, cauda_log: str = "", aplicar_editais: bool = True) -> ExecucaoRotina:
    """Aplica os editais da pasta (se pedido), grava e devolve o registo da execução."""
    editais = aplicar_editais_da_pasta(db, pasta_editais) if aplicar_editais else {
        "aplicados": [], "problemas": [], "ignorados": []}
    resumo_ed = resumo_editais(db, pasta_editais)
    resumo = {
        "codigo_saida": codigo_saida,
        "significado": significado(codigo_saida),
        "lista": _lista_desta_execucao(db, iniciada_em),
        "editais_aplicados": editais["aplicados"],
        "editais_com_problema": editais["problemas"],
        "editais_ignorados": editais["ignorados"],
        "pendentes_de_datas": resumo_ed.get("pendentes_de_datas", 0),
        "pendentes_por_uf": resumo_ed.get("pendentes_por_uf", {}),
        "ultimo_edital": resumo_ed.get("ultimo_edital"),
        "experimentar": resumo_ed.get("experimentar", []),
        "cauda_log": cauda_log[-2000:] if codigo_saida not in (0,) else "",
    }
    execucao = ExecucaoRotina(iniciada_em=iniciada_em, terminada_em=datetime.utcnow(),
                              codigo_saida=codigo_saida, resumo=json.dumps(resumo, ensure_ascii=False, default=str))
    db.add(execucao)
    db.commit()
    db.refresh(execucao)
    return execucao
