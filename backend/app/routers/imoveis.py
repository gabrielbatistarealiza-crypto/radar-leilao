from datetime import date, datetime
import re
import unicodedata
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import and_, or_, case, func
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.imovel import Imovel
from app.schemas.imovel import ImovelCreate, ImovelResponse, ImoveisPaginados
from app.utils.browser import Browser
from app.services.scraper_service import ScraperService


router = APIRouter(prefix="/imoveis", tags=["ImÃ³veis"])

def normalizar_texto(valor):
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", valor)
        if unicodedata.category(caractere) != "Mn"
    ).upper().strip()

def _imagem_caixa(url: Optional[str]):
    if not url:
        return None

    match = re.search(r"[?&]hdnimovel=(\d+)", url)
    if not match:
        return None

    return f"https://venda-imoveis.caixa.gov.br/fotos/F{match.group(1)}21.jpg"


def _score_expression():
    """
    Score global da oportunidade, calculado no PostgreSQL antes da paginaÃ§Ã£o.

    MÃ¡ximo: 100 pontos
      - Desconto:       40
      - Economia total: 20
      - Economia/mÂ²:    15
      - Dados essenciais: 15
      - Data do leilÃ£o: 10
    """

    desconto_pct = case(
        (
            and_(
                Imovel.valor_avaliacao.isnot(None),
                Imovel.valor_leilao.isnot(None),
                Imovel.valor_avaliacao > 0,
            ),
            (
                (Imovel.valor_avaliacao - Imovel.valor_leilao)
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
                Imovel.valor_leilao.isnot(None),
            ),
            Imovel.valor_avaliacao - Imovel.valor_leilao,
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
                Imovel.valor_leilao.isnot(None),
                Imovel.area.isnot(None),
                Imovel.area > 0,
            ),
            (Imovel.valor_avaliacao - Imovel.valor_leilao) / Imovel.area,
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
                    Imovel.valor_leilao.isnot(None),
                ),
                3,
            ),
            else_=0,
        )
    )

    hoje = date.today()

    proxima_data = case(
        (
            and_(
                Imovel.data_primeiro_leilao.isnot(None),
                Imovel.data_primeiro_leilao >= hoje,
            ),
            Imovel.data_primeiro_leilao,
        ),
        (
            and_(
                Imovel.data_segundo_leilao.isnot(None),
                Imovel.data_segundo_leilao >= hoje,
            ),
            Imovel.data_segundo_leilao,
        ),
        else_=None,
    )

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
    Adapta o modelo SQLAlchemy ao schema atual, que expÃµe `imagem`
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
        "valor_leilao": imovel.valor_leilao,
        "desconto": imovel.desconto,
        "economia_m2": imovel.economia_m2,
        "data_primeiro_leilao": imovel.data_primeiro_leilao,
        "data_segundo_leilao": imovel.data_segundo_leilao,
        "area": imovel.area,
        "quartos": imovel.quartos,
        "banheiros": imovel.banheiros,
        "vagas": imovel.vagas,
        "url": imovel.url,
        "imagem": imovel.url_imagem,
        "modalidade": imovel.modalidade,
        "fonte": imovel.fonte,
        "imagens": list(imovel.imagens or []),
    }


@router.get("/", response_model=ImoveisPaginados)
def listar_imoveis(
    cidade: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    modalidade: Optional[str] = Query("LeilÃ£o SFI - Edital Ãšnico"),
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
    query = db.query(Imovel)

    if cidade:
        cidade_normalizada = (
            cidade.strip()
            .upper()
            .replace("Ã", "A")
            .replace("Ã€", "A")
            .replace("Ãƒ", "A")
            .replace("Ã‚", "A")
            .replace("Ã‰", "E")
            .replace("ÃŠ", "E")
            .replace("Ã", "I")
            .replace("Ã“", "O")
            .replace("Ã”", "O")
            .replace("Ã•", "O")
            .replace("Ãš", "U")
            .replace("Ã‡", "C")
        )

        query = query.filter(
            func.translate(
                func.upper(Imovel.cidade),
                "ÃÃ€ÃƒÃ‚Ã‰ÃŠÃÃ“Ã”Ã•ÃšÃ‡",
                "AAAAEEIOOOUC",
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
                Imovel.valor_leilao.isnot(None),
                Imovel.valor_avaliacao > 0,
            ),
            (
                (Imovel.valor_avaliacao - Imovel.valor_leilao)
                / Imovel.valor_avaliacao
            ) * 100,
        ),
        else_=None,
    )

    if desconto_minimo is not None:
        query = query.filter(desconto_expr >= desconto_minimo)

    if valor_maximo is not None:
        query = query.filter(Imovel.valor_leilao <= valor_maximo)

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
    )

    condicao_sem_data = and_(
        Imovel.data_primeiro_leilao.is_(None),
        Imovel.data_segundo_leilao.is_(None),
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

    proxima_data = case(
        (
            and_(
                Imovel.data_primeiro_leilao.isnot(None),
                Imovel.data_primeiro_leilao >= hoje,
            ),
            Imovel.data_primeiro_leilao,
        ),
        (
            and_(
                Imovel.data_segundo_leilao.isnot(None),
                Imovel.data_segundo_leilao >= hoje,
            ),
            Imovel.data_segundo_leilao,
        ),
        else_=None,
    )

    if ordenar == "preco":
        campo = Imovel.valor_leilao
    elif ordenar == "desconto":
        campo = desconto_expr
    elif ordenar == "area":
        campo = Imovel.area
    elif ordenar == "economia_m2":
        campo = case(
            (
                and_(
                    Imovel.valor_avaliacao.isnot(None),
                    Imovel.valor_leilao.isnot(None),
                    Imovel.area.isnot(None),
                    Imovel.area > 0,
                ),
                (Imovel.valor_avaliacao - Imovel.valor_leilao) / Imovel.area,
            ),
            else_=None,
        )

    elif ordenar == "data":
        campo = proxima_data
    elif ordenar == "score":
        campo = _score_expression()
    else:
        campo = func.coalesce(
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

    for imovel in imoveis:
        if imovel.url_imagem:
            continue

        if (imovel.fonte or "").lower() != "caixa":
            continue

        imovel.url_imagem = _imagem_caixa(imovel.url)

    paginas_totais = (
        (total + tamanho_pagina - 1) // tamanho_pagina
        if total
        else 0
    )

    return {
        "items": [_serializar_imovel(imovel) for imovel in imoveis],
        "total": total,
        "pagina": pagina,
        "tamanho_pagina": tamanho_pagina,
        "paginas_totais": paginas_totais,
    }

@router.post("/manutencao/coletar-imagens-caixa-lote")
def coletar_imagens_caixa_lote(
    offset: int = Query(0, ge=0),
    limite: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Coleta as galerias da Caixa em lote usando uma Ãºnica
    sessÃ£o Playwright.

    offset:
        Quantidade de imÃ³veis a pular antes de iniciar.

    limite:
        Quantidade mÃ¡xima de imÃ³veis processados neste lote.
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

    try:
        browser.iniciar()

        for imovel in imoveis:
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

                # Descobre quais URLs jÃ¡ existem antes de salvar.
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

                # Salva somente atravÃ©s do serviÃ§o jÃ¡ validado.
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
        "resultado": resultados,
    }

@router.post("/manutencao/coletar-imagens-caixa-playwright")
def coletar_imagens_caixa_playwright(
    imovel_id: int = Query(...),
    db: Session = Depends(get_db),
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
            detail="ImÃ³vel Caixa nÃ£o encontrado.",
        )

    imagens, fotos_lidas = Browser().coletar_imagens_galeria(imovel.url)
    salvas = ScraperService(db).salvar_imagens(imovel, imagens)

    return {
        "id": imovel.id,
        "titulo": imovel.titulo,
        "fotos_encontradas": fotos_lidas,
        "fotos_salvas": len(imagens) if salvas else 0,
        "duplicadas": fotos_lidas - len(imagens),
        "imagens": imagens,
    }

@router.post("/manutencao/processar-fila-fotos-caixa")
def processar_fila_fotos_caixa(
    limite: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Processa um lote de imÃ³veis Caixa pendentes de fotos."""
    return ScraperService(db).processar_fila_fotos_caixa(limite)


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
            detail="ImÃ³vel nÃ£o encontrado.",
        )

    return _serializar_imovel(imovel)


@router.post("/manutencao/testar-galeria-caixa-playwright")
def testar_galeria_caixa_playwright(
    limite: int = Query(10, ge=1, le=10),
    db: Session = Depends(get_db),
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

    for imovel in imoveis:
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

            if any(
                termo in erro
                for termo in (
                    "CAPTCHA",
                    "PROTEÃ‡ÃƒO",
                    "PROTECAO",
                    "BOT MANAGER",
                )
            ):
                continue

    return {
        "processados": len(resultados),
        "limite": limite,
        "encontrado": encontrado,
        "resultado": resultados,
    }
