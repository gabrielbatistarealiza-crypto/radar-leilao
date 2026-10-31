from datetime import date, datetime
import os

import re

import time

import unicodedata

from typing import Optional, Literal, List



from fastapi import APIRouter, Depends, Query, HTTPException

from sqlalchemy import and_, or_, case, func

from sqlalchemy.orm import Session



from app.database.database import get_db

from app.models.imovel import Imovel, ImovelEvento, ImovelImagem

from app.schemas.imovel import ImovelCreate, ImovelEvento as ImovelEventoSchema, ImovelResponse, ImoveisPaginados

from app.utils.browser import Browser, CaixaBloqueioError
from app.services.caixa_acesso import (
    acesso_caixa_http,
    intervalo_entre_fotos,
    registrar_bloqueio_caixa,
)

from app.services.scraper_service import ScraperService
from app.security.auth import usuario_admin





router = APIRouter(prefix="/imoveis", tags=["Imóveis"])


def _porteiro_caixa(origem: str):
    """Dependência que só deixa o endpoint correr com acesso à CAIXA autorizado.

    Depende de usuario_admin, por isso a autenticação é resolvida ANTES do
    porteiro: sem login dá 401, sem perfil de administrador dá 403, e nesses
    casos o lock nunca é adquirido nem o estado de bloqueio é revelado.
    Usa o mesmo get_db do endpoint (a sessão é partilhada no pedido).
    Depois: 409 se outra consulta estiver em curso; 429 durante a espera.
    """

    def dependencia(
        administrador=Depends(usuario_admin),
        db: Session = Depends(get_db),
    ):
        # Estes endpoints abrem um browser (Selenium/Playwright) na CAIXA. As
        # fotos passaram a vir da própria página lida pelo worker de datas (só
        # requests). Ficam desligados salvo decisão explícita de os usar.
        if os.getenv("RADAR_PERMITIR_SELENIUM_CAIXA") != "1":
            raise HTTPException(
                status_code=410,
                detail=(
                    "Coleta de fotos com browser desativada. As fotos são "
                    "recolhidas pelo worker de datas, na mesma consulta da página."
                ),
            )
        with acesso_caixa_http(db, origem):
            yield

    return dependencia



def normalizar_texto(valor):

    return "".join(

        caractere

        for caractere in unicodedata.normalize("NFD", valor)

        if unicodedata.category(caractere) != "Mn"

    ).upper().strip()



def _proxima_data_leilao_expr(hoje):
    """Retorna a menor data futura entre as datas conhecidas do evento."""
    datas = (
        Imovel.data_primeiro_leilao,
        Imovel.data_segundo_leilao,
        Imovel.data_licitacao_aberta,
    )
    candidatas = []
    for candidata in datas:
        comparacoes = [
            or_(outra.is_(None), outra < hoje, candidata <= outra)
            for outra in datas
            if outra is not candidata
        ]
        candidatas.append(
            (and_(candidata.isnot(None), candidata >= hoje, *comparacoes), candidata)
        )
    return case(*candidatas, else_=None)


def _score_expression():

    """

    Score global da oportunidade, calculado no PostgreSQL antes da paginação.



    Máximo: 100 pontos

      - Desconto:       40

      - Economia total: 20

      - Economia/m²:    15

      - Dados essenciais: 15

      - Data do leilão: 10

    """



    desconto_pct = case(

        (

            and_(

                Imovel.valor_avaliacao.isnot(None),

                Imovel.valor_lance.isnot(None),

                Imovel.valor_avaliacao > 0,

            ),

            (

                (Imovel.valor_avaliacao - Imovel.valor_lance)

                / Imovel.valor_avaliacao

            ) * 100,

        ),

        else_=None,

    )



    desconto_pontos = case(

        (desconto_pct.is_(None), 0),

        (desconto_pct <= 0, 0),

        (desconto_pct >= 40, 40),

        else_=func.round(desconto_pct),

    )



    economia = case(

        (

            and_(

                Imovel.valor_avaliacao.isnot(None),

                Imovel.valor_lance.isnot(None),

            ),

            Imovel.valor_avaliacao - Imovel.valor_lance,

        ),

        else_=None,

    )



    economia_pontos = case(

        (economia >= 100000, 20),

        (economia >= 50000, 16),

        (economia >= 30000, 12),

        (economia >= 15000, 8),

        (economia >= 5000, 4),

        else_=0,

    )



    economia_m2 = case(

        (

            and_(

                Imovel.valor_avaliacao.isnot(None),

                Imovel.valor_lance.isnot(None),

                Imovel.area.isnot(None),

                Imovel.area > 0,

            ),

            (Imovel.valor_avaliacao - Imovel.valor_lance) / Imovel.area,

        ),

        else_=None,

    )



    economia_m2_pontos = case(

        (economia_m2 >= 2000, 15),

        (economia_m2 >= 1500, 12),

        (economia_m2 >= 1000, 9),

        (economia_m2 >= 500, 6),

        (economia_m2 >= 250, 3),

        else_=0,

    )



    dados_pontos = (

        case((desconto_pct.isnot(None), 4), else_=0)

        + case((Imovel.area.isnot(None), 4), else_=0)

        + case(

            (

                and_(

                    Imovel.cidade.isnot(None),

                    Imovel.estado.isnot(None),

                ),

                4,

            ),

            else_=0,

        )

        + case(

            (

                and_(

                    Imovel.valor_avaliacao.isnot(None),

                    Imovel.valor_lance.isnot(None),

                ),

                3,

            ),

            else_=0,

        )

    )



    hoje = date.today()



    proxima_data = _proxima_data_leilao_expr(hoje)

    dias = case(

        (proxima_data.isnot(None), proxima_data - hoje),

        else_=None,

    )







    data_pontos = case(

        (dias <= 30, 10),

        (dias <= 90, 8),

        (dias <= 180, 5),

        (dias > 180, 2),

        else_=0,

    )



    return (

        desconto_pontos

        + economia_pontos

        + economia_m2_pontos

        + dados_pontos

        + data_pontos

    )





def _serializar_imovel(imovel):

    """

    Adapta o modelo SQLAlchemy ao schema atual, que expõe `imagem`

    e `imagens`.

    """

    return {

        "id": imovel.id,

        "titulo": imovel.titulo,

        "tipo": imovel.tipo,

        "endereco": imovel.endereco,

        "cidade": imovel.cidade,

        "estado": imovel.estado,

        "valor_avaliacao": imovel.valor_avaliacao,

        # valor_leilao = lance mínimo (edital, se lido; senão o preço da lista),
        # para todos os cálculos do site usarem o preço que de facto se paga.
        "valor_leilao": imovel.valor_lance,

        "valor_lista": imovel.valor_leilao,

        "valor_primeiro_leilao": imovel.valor_primeiro_leilao,

        "valor_segundo_leilao": imovel.valor_segundo_leilao,

        "desconto": imovel.desconto_atual,

        "economia_m2": imovel.economia_m2,

        "data_primeiro_leilao": imovel.data_primeiro_leilao,

        "data_segundo_leilao": imovel.data_segundo_leilao,

        "data_licitacao_aberta": imovel.data_licitacao_aberta,

        "area": imovel.area,

        "quartos": imovel.quartos,

        "banheiros": imovel.banheiros,

        "vagas": imovel.vagas,

        "url": imovel.url,

        "imagem": imovel.url_imagem,

        "modalidade": imovel.modalidade,

        "fonte": imovel.fonte,

        "link_edital": imovel.link_edital,

        "leiloeiro": imovel.leiloeiro,

        "processo": imovel.processo,

        "ocupado": imovel.ocupado,

        "aceita_fgts": imovel.aceita_fgts,

        "aceita_financiamento": imovel.aceita_financiamento,

        "imagens": imovel.imagens or [],

        "na_lista": imovel.na_lista is not False,

        "saiu_da_lista_em": imovel.saiu_da_lista_em,

    }





@router.get("/", response_model=ImoveisPaginados)

def listar_imoveis(

    cidade: Optional[str] = Query(None),

    estado: Optional[str] = Query(None),

    tipo: Optional[str] = Query(None),

    busca: Optional[str] = Query(None, max_length=120),

    modalidade: Optional[str] = Query("Leilão SFI - Edital Único"),

    desconto_minimo: Optional[float] = Query(None),

    valor_maximo: Optional[float] = Query(None),

    area_min: Optional[float] = Query(None),

    area_max: Optional[float] = Query(None),

    quartos: Optional[int] = Query(None),

    banheiros: Optional[int] = Query(None),

    vagas: Optional[int] = Query(None),



    status_leilao: Literal[

        "ativos",

        "encerrados",

        "sem_data",

        "todos",

    ] = Query("ativos"),



    pagina: int = Query(1, ge=1),

    tamanho_pagina: int = Query(20, ge=1, le=100),

    ordenar: Literal[

        "preco",

        "desconto",

        "area",

        "economia_m2",

        "data",

        "score",



    ] = Query("preco"),

    direcao: Optional[Literal["asc", "desc"]] = Query(None),

    db: Session = Depends(get_db),

):

    # Imóveis que saíram da lista da Caixa ficam na base, mas não aparecem na pesquisa.
    query = db.query(Imovel).filter(Imovel.na_lista.is_(True))

    termo_busca = (busca or "").strip()
    if termo_busca:
        termo_escapado = (
            termo_busca.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        padrao_busca = f"%{termo_escapado}%"
        query = query.filter(
            or_(
                Imovel.titulo.ilike(padrao_busca, escape="\\"),
                Imovel.cidade.ilike(padrao_busca, escape="\\"),
                Imovel.estado.ilike(padrao_busca, escape="\\"),
                Imovel.tipo.ilike(padrao_busca, escape="\\"),
                Imovel.endereco.ilike(padrao_busca, escape="\\"),
            )
        )



    if cidade:

        cidade_normalizada = (

            cidade.strip()

            .upper()

            .replace("Á", "A")

            .replace("À", "A")

            .replace("Ã", "A")

            .replace("Â", "A")

            .replace("É", "E")

            .replace("Ê", "E")

            .replace("Í", "I")

            .replace("Ó", "O")

            .replace("Ô", "O")

            .replace("Õ", "O")

            .replace("Ú", "U")

            .replace("Ç", "C")

        )



        # Tira os acentos nas duas caixas e deixa o ilike ignorar maiúsculas:
        # upper() em letras acentuadas depende do locale da base (no locale C
        # "são" fica "SãO" e a pesquisa por "sao paulo" não encontrava nada).
        query = query.filter(

            func.translate(

                Imovel.cidade,

                "ÁÀÃÂÉÊÍÓÔÕÚÇáàãâéêíóôõúç",

                "AAAAEEIOOOUCaaaaeeiooouc",

            ).ilike(f"%{cidade_normalizada}%")

        )



    if estado:

        query = query.filter(Imovel.estado == estado)



    if tipo:

        query = query.filter(Imovel.tipo == tipo)



    if modalidade:

        query = query.filter(Imovel.modalidade == modalidade)



    desconto_expr = case(

        (

            and_(

                Imovel.valor_avaliacao.isnot(None),

                Imovel.valor_lance.isnot(None),

                Imovel.valor_avaliacao > 0,

            ),

            (

                (Imovel.valor_avaliacao - Imovel.valor_lance)

                / Imovel.valor_avaliacao

            ) * 100,

        ),

        else_=None,

    )



    if desconto_minimo is not None:

        query = query.filter(desconto_expr >= desconto_minimo)



    if valor_maximo is not None:

        query = query.filter(Imovel.valor_lance <= valor_maximo)



    if area_min is not None:

        query = query.filter(Imovel.area >= area_min)



    if area_max is not None:

        query = query.filter(Imovel.area <= area_max)



    if quartos is not None:

        query = query.filter(Imovel.quartos == quartos)



    if banheiros is not None:

        query = query.filter(Imovel.banheiros == banheiros)



    if vagas is not None:

        query = query.filter(Imovel.vagas == vagas)



    hoje = date.today()



    condicao_ativo = or_(

        and_(

            Imovel.data_primeiro_leilao.isnot(None),

            Imovel.data_primeiro_leilao >= hoje,

        ),

        and_(

            Imovel.data_segundo_leilao.isnot(None),

            Imovel.data_segundo_leilao >= hoje,

        ),

        and_(

            Imovel.data_licitacao_aberta.isnot(None),

            Imovel.data_licitacao_aberta >= hoje,

        ),

    )



    condicao_sem_data = and_(

        Imovel.data_primeiro_leilao.is_(None),

        Imovel.data_segundo_leilao.is_(None),

        Imovel.data_licitacao_aberta.is_(None),

    )



    condicao_encerrado = and_(

        ~condicao_ativo,

        ~condicao_sem_data,

    )



    if status_leilao == "ativos":

        query = query.filter(condicao_ativo)



    elif status_leilao == "encerrados":

        query = query.filter(condicao_encerrado)



    elif status_leilao == "sem_data":

        query = query.filter(condicao_sem_data)



    total = query.count()



    proxima_data = _proxima_data_leilao_expr(hoje)

    if ordenar == "preco":

        campo = Imovel.valor_lance

    elif ordenar == "desconto":

        campo = desconto_expr

    elif ordenar == "area":

        campo = Imovel.area

    elif ordenar == "economia_m2":

        campo = case(

            (

                and_(

                    Imovel.valor_avaliacao.isnot(None),

                    Imovel.valor_lance.isnot(None),

                    Imovel.area.isnot(None),

                    Imovel.area > 0,

                ),

                (Imovel.valor_avaliacao - Imovel.valor_lance) / Imovel.area,

            ),

            else_=None,

        )



    elif ordenar == "data":

        campo = proxima_data

    elif ordenar == "score":

        campo = _score_expression()

    else:

        campo = func.coalesce(

            Imovel.data_licitacao_aberta,

            Imovel.data_segundo_leilao,

            Imovel.data_primeiro_leilao,

        )



    if direcao is None:

        direcao = "asc" if ordenar in ("preco", "data") else "desc"



    if direcao == "asc":

        query = query.order_by(campo.asc().nullslast(), Imovel.id.asc())

    else:

        query = query.order_by(campo.desc().nullslast(), Imovel.id.asc())



    offset = (pagina - 1) * tamanho_pagina

    imoveis = (

        query

        .offset(offset)

        .limit(tamanho_pagina)

        .all()

    )



    items = []

    for imovel in imoveis:
        resultado = _serializar_imovel(imovel)
        imagens = [
            foto
            for foto in (imovel.imagens or [])
            if isinstance(foto, str) and foto.strip()
        ]

        if imagens:
            resultado["imagens"] = imagens
            resultado["imagem"] = imagens[0]
        elif imovel.url_imagem:
            resultado["imagens"] = [imovel.url_imagem]
            resultado["imagem"] = imovel.url_imagem
        else:
            resultado["imagens"] = []
            resultado["imagem"] = None

        items.append(resultado)

    paginas_totais = (

        (total + tamanho_pagina - 1) // tamanho_pagina

        if total

        else 0

    )



    return {

        "items": items,

        "total": total,

        "pagina": pagina,

        "tamanho_pagina": tamanho_pagina,

        "paginas_totais": paginas_totais,

    }



@router.post(
    "/manutencao/coletar-imagens-caixa-lote",
    dependencies=[Depends(_porteiro_caixa("fotos-lote-manual"))],
)

def coletar_imagens_caixa_lote(

    offset: int = Query(0, ge=0),

    limite: int = Query(10, ge=1, le=100),

    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),

):

    """

    Coleta as galerias da Caixa em lote usando uma única

    sessão Playwright.



    offset:

        Quantidade de imóveis a pular antes de iniciar.



    limite:

        Quantidade máxima de imóveis processados neste lote.

    """



    total = (

        db.query(Imovel)

        .filter(

            Imovel.fonte.ilike("%caixa%"),

            Imovel.url.isnot(None),

        )

        .count()

    )



    imoveis = (

        db.query(Imovel)

        .filter(

            Imovel.fonte.ilike("%caixa%"),

            Imovel.url.isnot(None),

        )

        .order_by(Imovel.id.asc())

        .offset(offset)

        .limit(limite)

        .all()

    )



    browser = Browser()



    resultados = []



    processados = 0

    sucesso = 0

    sem_fotos = 0

    falhas = 0

    fotos_encontradas_total = 0

    fotos_novas = 0

    fotos_existentes = 0



    bloqueado = False
    pausa = intervalo_entre_fotos()

    try:

        browser.iniciar()



        for imovel in imoveis:

            if processados:
                time.sleep(pausa)

            processados += 1



            resultado = {

                "id": imovel.id,

                "titulo": imovel.titulo,

                "fotos_encontradas": 0,

                "fotos_novas": 0,

                "fotos_existentes": 0,

                "status": None,

                "erro": None,

            }



            try:

                print(

                    f"\n[{processados}/{len(imoveis)}] "

                    f"ID {imovel.id} - {imovel.titulo}"

                )



                imagens, fotos_lidas = (

                    browser.coletar_imagens_galeria_sessao(

                        imovel.url

                    )

                )



                resultado["fotos_encontradas"] = fotos_lidas

                fotos_encontradas_total += fotos_lidas



                if not imagens:

                    sem_fotos += 1

                    resultado["status"] = "sem_fotos"



                    print(

                        f"[SEM FOTOS] ID {imovel.id}"

                    )



                    resultados.append(resultado)

                    continue



                # Descobre quais URLs já existem antes de salvar.

                urls_existentes = {

                    foto.url

                    for foto in imovel.fotos

                }



                novas = [

                    imagem

                    for imagem in imagens

                    if imagem not in urls_existentes

                ]



                existentes = [

                    imagem

                    for imagem in imagens

                    if imagem in urls_existentes

                ]



                # Salva somente através do serviço já validado.

                ScraperService(db).salvar_imagens(

                    imovel,

                    imagens,

                )



                # Garante que a primeira foto seja a imagem principal.

                if not imovel.url_imagem and imagens:

                    imovel.url_imagem = imagens[0]

                    db.add(imovel)

                    db.commit()



                resultado["fotos_novas"] = len(novas)

                resultado["fotos_existentes"] = len(existentes)

                resultado["status"] = "sucesso"



                fotos_novas += len(novas)

                fotos_existentes += len(existentes)

                sucesso += 1



                resultados.append(resultado)



                print(

                    f"[OK] novas={len(novas)} "

                    f"existentes={len(existentes)}"

                )



            except CaixaBloqueioError as exc:

                # CAPTCHA/bloqueio: grava a espera partilhada e para o lote.
                # Este imóvel não conta como processado (o offset não o salta).
                processados -= 1
                bloqueado = True
                resultado["status"] = "bloqueado"
                resultado["erro"] = str(exc)
                resultados.append(resultado)
                registrar_bloqueio_caixa(db, "fotos-lote-manual")
                break

            except Exception as exc:

                falhas += 1



                resultado["status"] = "erro"

                resultado["erro"] = str(exc)



                print(

                    f"[ERRO] ID {imovel.id}: {exc}"

                )



                resultados.append(resultado)



    finally:

        browser.fechar()



    proximo_offset = offset + processados



    return {

        "total_banco": total,

        "offset": offset,

        "limite": limite,

        "processados": processados,

        "proximo_offset": proximo_offset,

        "restantes": max(total - proximo_offset, 0),

        "sucesso": sucesso,

        "sem_fotos": sem_fotos,

        "falhas": falhas,

        "fotos_encontradas": fotos_encontradas_total,

        "fotos_novas": fotos_novas,

        "fotos_existentes": fotos_existentes,

        "bloqueado": bloqueado,

        "resultado": resultados,

    }



@router.post(
    "/manutencao/coletar-imagens-caixa-playwright",
    dependencies=[Depends(_porteiro_caixa("fotos-imovel-manual"))],
)

def coletar_imagens_caixa_playwright(

    imovel_id: int = Query(...),

    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),

):

    imovel = (

        db.query(Imovel)

        .filter(

            Imovel.id == imovel_id,

            Imovel.fonte.ilike("%caixa%"),

        )

        .first()

    )



    if not imovel:

        raise HTTPException(

            status_code=404,

            detail="Imóvel Caixa não encontrado.",

        )



    try:
        imagens, fotos_lidas = Browser().coletar_imagens_galeria(imovel.url)
    except CaixaBloqueioError as exc:
        horas = registrar_bloqueio_caixa(db, "fotos-imovel-manual")
        raise HTTPException(
            status_code=429,
            detail=(
                "A CAIXA bloqueou o acesso. Novas consultas suspensas por "
                f"{horas} horas."
            ),
        ) from exc

    salvas = ScraperService(db).salvar_imagens(imovel, imagens)



    return {

        "id": imovel.id,

        "titulo": imovel.titulo,

        "fotos_encontradas": fotos_lidas,

        "fotos_salvas": len(imagens) if salvas else 0,

        "duplicadas": fotos_lidas - len(imagens),

        "imagens": imagens,

    }



@router.post(
    "/manutencao/processar-fila-fotos-caixa",
    dependencies=[Depends(_porteiro_caixa("fotos-fila-manual"))],
)

def processar_fila_fotos_caixa(

    limite: int = Query(10, ge=1, le=100),

    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),

):

    """Processa um lote de imóveis Caixa pendentes de fotos."""

    resultado = ScraperService(db).processar_fila_fotos_caixa(limite)
    if resultado.get("bloqueados", 0):
        resultado["horas_espera"] = registrar_bloqueio_caixa(db, "fotos-fila-manual")
    return resultado


# Vitrine do ecrã de entrada (sem sessão): poucos campos, só o necessário.
# Tem de ficar antes de "/{imovel_id}" para "destaques" não ser lido como id.
@router.get("/destaques")
def imoveis_em_destaque(
    limite: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Imóveis na lista, com foto, leilão por acontecer e maior desconto; uma cidade cada."""
    hoje = date.today()
    desconto = (Imovel.valor_avaliacao - Imovel.valor_lance) / Imovel.valor_avaliacao * 100
    tem_foto = or_(
        Imovel.url_imagem.isnot(None),
        db.query(ImovelImagem.id).filter(ImovelImagem.imovel_id == Imovel.id).exists(),
    )
    candidatos = (
        db.query(Imovel)
        .filter(
            Imovel.na_lista.is_(True),
            Imovel.valor_avaliacao > 0,
            Imovel.valor_lance > 0,
            desconto > 0,
            or_(Imovel.data_primeiro_leilao >= hoje, Imovel.data_segundo_leilao >= hoje),
            tem_foto,
        )
        .order_by(desconto.desc(), Imovel.id)
        .limit(limite * 15)
        .all()
    )
    escolhidos, cidades = [], set()
    for imovel in candidatos:  # uma por cidade, para a vitrine não ficar só de um sítio
        cidade = (imovel.cidade or "").strip().upper()
        if cidade in cidades:
            continue
        cidades.add(cidade)
        escolhidos.append(imovel)
        if len(escolhidos) == limite:
            break
    proximas = lambda i: [d for d in (i.data_primeiro_leilao, i.data_segundo_leilao) if d and d >= hoje]  # noqa: E731
    return [
        {
            "id": i.id,
            "tipo": i.tipo,
            "cidade": i.cidade,
            "estado": i.estado,
            "foto": (i.imagens or [None])[0] or i.url_imagem,
            "valor_avaliacao": i.valor_avaliacao,
            "valor_lance": i.valor_lance,
            "desconto": round(i.desconto_atual or 0, 1),
            "proximo_leilao": min(proximas(i), default=None),
        }
        for i in escolhidos
    ]


@router.get("/{imovel_id}/historico", response_model=list[ImovelEventoSchema])
def historico_imovel(imovel_id: int, db: Session = Depends(get_db)):
    """Entradas e saídas da lista da Caixa e mudanças de preço, do mais antigo ao mais recente."""
    if not db.query(Imovel.id).filter(Imovel.id == imovel_id).first():
        raise HTTPException(status_code=404, detail="Imóvel não encontrado.")
    return (
        db.query(ImovelEvento)
        .filter(ImovelEvento.imovel_id == imovel_id)
        .order_by(ImovelEvento.momento.asc(), ImovelEvento.id.asc())
        .all()
    )


@router.get("/{imovel_id}", response_model=ImovelResponse)

def buscar_imovel(

    imovel_id: int,

    db: Session = Depends(get_db),

):

    imovel = (

        db.query(Imovel)

        .filter(Imovel.id == imovel_id)

        .first()

    )



    if not imovel:

        raise HTTPException(

            status_code=404,

            detail="Imóvel não encontrado.",

        )



    resultado = _serializar_imovel(imovel)

    imagens = [
        foto
        for foto in (imovel.imagens or [])
        if isinstance(foto, str) and foto.strip()
    ]

    if not imagens and imovel.url_imagem:
        imagens = [imovel.url_imagem]

    resultado["imagens"] = imagens
    resultado["imagem"] = imagens[0] if imagens else None

    return resultado



@router.post(
    "/manutencao/testar-galeria-caixa-playwright",
    dependencies=[Depends(_porteiro_caixa("fotos-teste-manual"))],
)

def testar_galeria_caixa_playwright(

    limite: int = Query(10, ge=1, le=10),

    db: Session = Depends(get_db),
    administrador=Depends(usuario_admin),

):

    imoveis = (

        db.query(Imovel)

        .filter(Imovel.fonte.ilike("%caixa%"))

        .order_by(Imovel.id.asc())

        .limit(limite)

        .all()

    )



    resultados = []

    encontrado = None

    bloqueado = False

    pausa = intervalo_entre_fotos()



    for indice, imovel in enumerate(imoveis):

        if indice:
            time.sleep(pausa)

        resultado = {

            "id": imovel.id,

            "titulo": imovel.titulo,

            "fotos_encontradas": 0,

            "fotos_unicas": 0,

            "duplicadas": 0,

            "imagens": [],

            "erro": None,

        }



        try:

            imagens, fotos_lidas = Browser().coletar_imagens_galeria(imovel.url)



            resultado["fotos_encontradas"] = fotos_lidas

            resultado["fotos_unicas"] = len(imagens)

            resultado["duplicadas"] = fotos_lidas - len(imagens)

            resultado["imagens"] = imagens



            if len(imagens) >= 2:

                encontrado = resultado



            resultados.append(resultado)



            if encontrado:

                break



        except Exception as exc:

            resultado["erro"] = str(exc)

            resultados.append(resultado)



            erro = str(exc).upper()



            if isinstance(exc, CaixaBloqueioError) or any(

                termo in erro

                for termo in (

                    "CAPTCHA",

                    "PROTEÇÃO",

                    "PROTECAO",

                    "BOT MANAGER",

                )

            ):

                # Antes seguia para o imóvel seguinte com um navegador novo.
                # Agora grava a espera partilhada e para.
                bloqueado = True
                registrar_bloqueio_caixa(db, "fotos-teste-manual")
                break



    return {

        "processados": len(resultados),

        "limite": limite,

        "encontrado": encontrado,

        "bloqueado": bloqueado,

        "resultado": resultados,

    }
