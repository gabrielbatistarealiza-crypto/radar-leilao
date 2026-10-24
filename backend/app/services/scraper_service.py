import logging
import time

import re
from sqlalchemy import and_, not_, or_

from typing import List

from datetime import datetime

from sqlalchemy.orm import Session



from app.models.imovel import Imovel, ImovelImagem, ImovelFotoVerificacao

from app.schemas.imovel_scraper import ImovelScraper

from app.scrapers.caixa import CaixaFalhaTecnicaError, CaixaScraper
from app.services.caixa_datas_worker import reativar_worker_datas_caixa
from app.services.caixa_acesso import intervalo_entre_fotos, registrar_bloqueio_caixa

from app.services.caixa_downloader import CaixaDownloader

from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.oportunidade import Oportunidade

from app.utils.browser import Browser, CaixaBloqueioError



logger = logging.getLogger(__name__)





class ScraperService:



    def __init__(self, db: Session):

        self.db = db
        self.urls_vistas: set[str] = set()



    def executar_scraper_caixa(self) -> List[Imovel]:

        """Executa o scraper da Caixa e salva/atualiza os imóveis no banco."""

        self.urls_vistas = set()

        scraper = CaixaScraper()

        dados_imoveis: List[ImovelScraper] = scraper.executar()



        print("DEBUG SCRAPER - QUANTIDADE:", len(dados_imoveis))

        print("DEBUG SCRAPER - PRIMEIROS:", dados_imoveis[:2])



        imoveis_salvos = []



        for imovel_dto in dados_imoveis:

            try:

                # 1. Mapeamento explícito de campos (resolve area_util -> area)

                dados_dict = imovel_dto.model_dump(

                    exclude={"imagens", "imagem", "imagem_url"}

                )



                # Trata equivalência de área

                area_valor = dados_dict.pop("area_util", None) or dados_dict.get("area")

                dados_dict["area"] = area_valor

                if "area_util" in dados_dict:

                    del dados_dict["area_util"]



                url_imovel = dados_dict.get("url")



                if url_imovel:

                    url_texto = str(url_imovel).strip()



                    match_id = re.search(

                        r"hdnimovel=([0-9]+)",

                        url_texto,

                        re.IGNORECASE

                    )



                    if match_id:

                        url_imovel = (

                            "https://venda-imoveis.caixa.gov.br/"

                            "sistema/detalhe-imovel.asp?hdnimovel="

                            + match_id.group(1)

                        )

                    else:

                        url_imovel = url_texto



                    dados_dict["url"] = url_imovel

                    # Conta a URL já aqui: mesmo que o salvamento falhe depois, o imóvel
                    # continua na lista da Caixa e não pode ser tratado como removido.
                    self.urls_vistas.add(url_imovel)





                # 2. Verifica se o imóvel já existe no banco (via URL ou Titulo/Endereco)

                imovel_existente = None

                if url_imovel:

                    imovel_existente = (

                        self.db.query(Imovel)

                        .filter(Imovel.url == url_imovel)

                        .first()

                    )



                if imovel_existente:

                    # Atualiza os dados existentes

                    for chave, valor in dados_dict.items():

                        if valor is not None:

                            setattr(imovel_existente, chave, valor)

                    imovel_db = imovel_existente

                else:

                    # Cria novo registro

                    imovel_db = Imovel(**dados_dict)

                    self.db.add(imovel_db)

                    self.db.flush()  # Gera o ID para as imagens



                # 3. Processamento e salvamento das imagens associadas

                urls_imagens = imovel_dto.imagens or []

                if imovel_dto.imagem and imovel_dto.imagem not in urls_imagens:

                    urls_imagens.insert(0, imovel_dto.imagem)



                for ordem, url_img in enumerate(urls_imagens):

                    if not url_img:

                        continue



                    img_existente = (

                        self.db.query(ImovelImagem)

                        .filter(

                            ImovelImagem.imovel_id == imovel_db.id,

                            ImovelImagem.url == url_img,

                        )

                        .first()

                    )



                    if not img_existente:

                        nova_imagem = ImovelImagem(

                            imovel_id=imovel_db.id,

                            url=url_img,

                            ordem=ordem

                        )

                        self.db.add(nova_imagem)



                self.db.commit()

                self.db.refresh(imovel_db)

                imoveis_salvos.append(imovel_db)



            except Exception as e:

                self.db.rollback()

                logger.exception(
                    f"ERRO AO SALVAR IMÓVEL {imovel_dto.titulo}: "
                    f"{type(e).__name__}: {e}"

                )



                continue



        return imoveis_salvos



    def preparar_fila_fotos_caixa(self, imoveis: List[Imovel]) -> dict:
        """Prepara o status de coleta de fotos dos imÃƒÂ³veis Caixa."""

        pendentes = 0

        com_fotos = 0

        sem_fotos = 0



        for imovel in imoveis:

            if not imovel.id:

                continue



            verificacao = (

                self.db.query(ImovelFotoVerificacao)

                .filter(

                    ImovelFotoVerificacao.imovel_id == imovel.id

                )

                .first()

            )



            possui_fotos = (

                self.db.query(ImovelImagem.id)

                .filter(

                    ImovelImagem.imovel_id == imovel.id

                )

                .first()

                is not None

            )



            if possui_fotos:

                resultado = "COM_FOTOS"

                com_fotos += 1

            elif verificacao is None:

                resultado = "PENDENTE"

                pendentes += 1

            elif verificacao.resultado in ("BLOQUEADO", "ERRO"):

                resultado = "PENDENTE"

                pendentes += 1

            else:

                resultado = verificacao.resultado

                if resultado == "SEM_FOTOS":

                    sem_fotos += 1



            if verificacao is None:

                verificacao = ImovelFotoVerificacao(

                    imovel_id=imovel.id,

                    resultado=resultado,

                )

                self.db.add(verificacao)

            elif verificacao.resultado != resultado:

                verificacao.resultado = resultado

                verificacao.verificado_em = datetime.utcnow()



        self.db.commit()



        return {

            "pendentes": pendentes,

            "com_fotos": com_fotos,

            "sem_fotos": sem_fotos,

        }



    def atualizar_lista_caixa(self) -> dict:

        """Baixa, importa e remove anuncios Caixa ausentes da lista atual."""



        atualizacao = AtualizacaoCaixa(

            status="EXECUTANDO",

            iniciada_em=datetime.utcnow(),

        )



        self.db.add(atualizacao)

        self.db.commit()

        self.db.refresh(atualizacao)



        try:

            download = CaixaDownloader().baixar_todos()

            if download.get("bloqueado"):
                # CAPTCHA no download: grava a espera partilhada. Os CSVs que já
                # estavam no disco continuam a ser lidos; a limpeza de imóveis
                # ausentes não corre porque o download ficou incompleto.
                registrar_bloqueio_caixa(self.db, "importacao")

            imoveis = self.executar_scraper_caixa()



            estados_esperados = set(CaixaDownloader.UFS)

            estados_baixados = set(download.get("sucesso", []))

            urls_ativas = set(self.urls_vistas) | {
                imovel.url
                for imovel in imoveis
                if imovel.url
            }



            removidos = 0



            # So removemos anuncios quando a lista nacional foi baixada por inteiro.

            # Em uma atualizacao parcial, arquivos ausentes nao podem ser tratados

            # como se os respectivos imoveis tivessem saido da Caixa.

            if estados_baixados == estados_esperados and urls_ativas:

                removidos = self._remover_imoveis_caixa_inativos(

                    urls_ativas

                )

            else:

                logger.warning(

                    "Limpeza de imoveis Caixa ignorada: "

                    "download incompleto ou sem URLs."

                )



            fila_fotos = self.preparar_fila_fotos_caixa(imoveis)



            atualizacao.status = "CONCLUIDA"

            atualizacao.concluida_em = datetime.utcnow()

            atualizacao.imoveis_atualizados = len(imoveis)

            atualizacao.imoveis_removidos = removidos

            atualizacao.fotos_pendentes = fila_fotos.get(

                "pendentes",

                0,

            )

            atualizacao.estados_baixados = len(

                download.get("sucesso", [])

            )

            # Novos imóveis entram sem datas (o CSV não as traz): volta a pôr a
            # fila de datas a correr desde o início. Não mexe num bloqueio ativo.
            reativar_worker_datas_caixa(self.db)



            self.db.commit()



            return {

                "download": download,

                "imoveis_atualizados": len(imoveis),

                "imoveis_removidos": removidos,

                "fila_fotos": fila_fotos,

            }



        except Exception as exc:

            self.db.rollback()



            atualizacao = (

                self.db.query(AtualizacaoCaixa)

                .filter(

                    AtualizacaoCaixa.id == atualizacao.id

                )

                .first()

            )



            if atualizacao:

                atualizacao.status = "ERRO"

                atualizacao.concluida_em = datetime.utcnow()

                atualizacao.erro = (

                    f"{type(exc).__name__}: {exc}"

                )

                self.db.commit()



            raise




    def enriquecer_datas_caixa(
        self,
        limite: int = 3,
        depois_id: int | None = None,
    ) -> dict:
        """Consulta uma pequena leva de anúncios para completar datas ausentes."""
        modalidade_licitacao_aberta = Imovel.modalidade.ilike(
            "%licitação aberta%"
        )
        pendencia_datas_leilao = or_(
            Imovel.data_primeiro_leilao.is_(None),
            Imovel.data_segundo_leilao.is_(None),
        )
        pendencia_data = or_(
            and_(
                modalidade_licitacao_aberta,
                Imovel.data_licitacao_aberta.is_(None),
            ),
            and_(
                or_(
                    Imovel.modalidade.is_(None),
                    not_(modalidade_licitacao_aberta),
                ),
                pendencia_datas_leilao,
            ),
        )
        consulta = self.db.query(Imovel).filter(
            Imovel.fonte.ilike("%caixa%"),
            Imovel.url.isnot(None),
            pendencia_data,
        )
        if depois_id is not None:
            consulta = consulta.filter(Imovel.id > depois_id)

        imoveis = consulta.order_by(Imovel.id.asc()).limit(limite).all()
        scraper = CaixaScraper()
        processados = 0
        atualizados = 0
        sem_dados = 0
        erros = 0
        falhas_tecnicas = 0
        falha_tecnica_id = None
        bloqueado = False
        resultados = []

        try:
            for imovel in imoveis:
                processados += 1
                try:
                    datas = scraper.extrair_datas_leilao(imovel.url)
                    campos = (
                        "data_primeiro_leilao",
                        "data_segundo_leilao",
                        "data_licitacao_aberta",
                    )
                    alterou = False
                    for campo, data in zip(campos, datas):
                        if getattr(imovel, campo) is None and data is not None:
                            setattr(imovel, campo, data)
                            alterou = True

                    if alterou:
                        atualizados += 1
                    else:
                        sem_dados += 1
                    resultados.append(
                        {
                            "id": imovel.id,
                            "titulo": imovel.titulo,
                            "status": "ATUALIZADO" if alterou else "SEM_DATAS_NOVAS",
                        }
                    )
                    if scraper.bloqueado:
                        bloqueado = True
                        resultados[-1]["status"] = "BLOQUEADO_CAIXA"
                        break
                except CaixaFalhaTecnicaError as erro:
                    # Não é "sem datas": a página não foi lida. Para a leva para
                    # quem chamou decidir se tenta o mesmo imóvel outra vez.
                    falhas_tecnicas += 1
                    falha_tecnica_id = imovel.id
                    logger.warning(
                        "Falha técnica ao ler datas do imóvel %s: %s",
                        imovel.id,
                        erro,
                    )
                    resultados.append(
                        {
                            "id": imovel.id,
                            "titulo": imovel.titulo,
                            "status": "FALHA_TECNICA",
                        }
                    )
                    break
                except Exception as erro:
                    erros += 1
                    logger.warning(
                        "Falha ao enriquecer datas do imóvel %s: %s",
                        imovel.id,
                        type(erro).__name__,
                    )
                    resultados.append(
                        {"id": imovel.id, "titulo": imovel.titulo, "status": "ERRO"}
                    )

            if atualizados:
                self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        finally:
            if scraper.driver:
                try:
                    scraper.driver.quit()
                except Exception:
                    pass
                scraper.driver = None

        # Último imóvel realmente consultado: se a leva parou a meio (bloqueio ou
        # falha técnica), os seguintes não podem ser dados como vistos.
        ultimo_id = imoveis[processados - 1].id if processados else depois_id
        tem_mais = bool(
            ultimo_id is not None
            and self.db.query(Imovel.id)
            .filter(
                Imovel.fonte.ilike("%caixa%"),
                Imovel.url.isnot(None),
                pendencia_data,
                Imovel.id > ultimo_id,
            )
            .first()
        )
        return {
            "processados": processados,
            "atualizados": atualizados,
            "sem_dados_novos": sem_dados,
            "erros": erros,
            "falhas_tecnicas": falhas_tecnicas,
            "falha_tecnica": falha_tecnica_id is not None,
            "falha_tecnica_id": falha_tecnica_id,
            "bloqueado": bloqueado,
            "tem_mais": tem_mais,
            "proximo_depois_id": ultimo_id if tem_mais else None,
            "resultados": resultados,
        }


    def _remover_imoveis_caixa_inativos(self, urls_ativas: set[str]) -> int:
        """Remove imóveis Caixa inativos sem apagar histórico comercial."""

        candidatos = (
            self.db.query(Imovel)
            .filter(
                Imovel.fonte.ilike("%caixa%"),
                Imovel.url.isnot(None),
            )
            .all()
        )

        inativos = [
            imovel
            for imovel in candidatos
            if imovel.url not in urls_ativas
        ]

        removidos = 0

        for imovel in inativos:
            # Preserva imóveis ligados a oportunidades ou negociações.
            tem_oportunidades = (
                self.db.query(Oportunidade.id)
                .filter(Oportunidade.imovel_id == imovel.id)
                .first()
                is not None
            )

            if tem_oportunidades:
                logger.warning(
                    "Imóvel Caixa %s ausente da lista atual, "
                    "mas preservado por ter oportunidades associadas.",
                    imovel.id,
                )
                continue

            self.db.query(ImovelFotoVerificacao).filter(
                ImovelFotoVerificacao.imovel_id == imovel.id
            ).delete(synchronize_session=False)

            self.db.query(ImovelImagem).filter(
                ImovelImagem.imovel_id == imovel.id
            ).delete(synchronize_session=False)

            self.db.delete(imovel)
            removidos += 1

        if removidos:
            self.db.commit()

        return removidos




    def processar_fila_fotos_caixa(

        self,

        limite: int = 10,

    ) -> dict:

        """Processa imóveis Caixa pendentes de coleta de fotos."""



        pendentes = (

            self.db.query(Imovel)

            .join(

                ImovelFotoVerificacao,

                ImovelFotoVerificacao.imovel_id == Imovel.id,

            )

            .filter(

                Imovel.fonte.ilike("%caixa%"),

                ImovelFotoVerificacao.resultado == "PENDENTE",

                Imovel.url.isnot(None),

            )

            .order_by(Imovel.id.asc())

            .limit(limite)

            .all()

        )



        total_pendentes = (

            self.db.query(ImovelFotoVerificacao)

            .join(

                Imovel,

                Imovel.id == ImovelFotoVerificacao.imovel_id,

            )

            .filter(

                Imovel.fonte.ilike("%caixa%"),

                ImovelFotoVerificacao.resultado == "PENDENTE",

            )

            .count()

        )



        processados = 0

        com_fotos = 0

        sem_fotos = 0

        bloqueados = 0

        erros = 0

        fotos_novas = 0

        resultados = []



        browser = Browser()



        try:

            browser.iniciar()

            pausa = intervalo_entre_fotos()

            for imovel in pendentes:

                # Espaça as páginas da CAIXA (antes só havia os 3 s da galeria).
                if processados:
                    time.sleep(pausa)

                processados += 1



                verificacao = (

                    self.db.query(ImovelFotoVerificacao)

                    .filter(

                        ImovelFotoVerificacao.imovel_id == imovel.id

                    )

                    .first()

                )



                try:

                    imagens, fotos_lidas = (

                        browser.coletar_imagens_galeria_sessao(

                            imovel.url

                        )

                    )



                    if not imagens:

                        verificacao.resultado = "SEM_FOTOS"

                        verificacao.verificado_em = datetime.utcnow()

                        self.db.commit()



                        sem_fotos += 1



                        resultados.append({

                            "id": imovel.id,

                            "status": "SEM_FOTOS",

                            "fotos": 0,

                        })



                        continue



                    urls_existentes = {

                        foto.url

                        for foto in imovel.fotos

                    }



                    novas = [

                        imagem

                        for imagem in imagens

                        if imagem not in urls_existentes

                    ]



                    self.salvar_imagens(imovel, imagens)



                    verificacao.resultado = "COM_FOTOS"

                    verificacao.verificado_em = datetime.utcnow()

                    self.db.commit()



                    com_fotos += 1

                    fotos_novas += len(novas)



                    resultados.append({

                        "id": imovel.id,

                        "status": "COM_FOTOS",

                        "fotos": len(imagens),

                        "fotos_novas": len(novas),

                    })



                except CaixaBloqueioError as exc:

                    verificacao.resultado = "PENDENTE"

                    verificacao.verificado_em = datetime.utcnow()

                    self.db.commit()



                    bloqueados += 1



                    resultados.append({

                        "id": imovel.id,

                        "status": "BLOQUEADO",

                        "erro": str(exc),

                    })



                    # Não continuar fazendo requisições

                    # depois que a Caixa bloqueou.

                    break



                except Exception as exc:

                    verificacao.resultado = "PENDENTE"

                    verificacao.verificado_em = datetime.utcnow()

                    self.db.commit()



                    erros += 1



                    logger.error(

                        f"Erro ao coletar fotos do imóvel "

                        f"{imovel.id}: {exc}"

                    )



                    resultados.append({

                        "id": imovel.id,

                        "status": "ERRO",

                        "erro": str(exc),

                    })



        finally:

            browser.fechar()



        restantes = max(

            total_pendentes - processados,

            0,

        )



        return {

            "total_pendentes_antes": total_pendentes,

            "processados": processados,

            "com_fotos": com_fotos,

            "sem_fotos": sem_fotos,

            "bloqueados": bloqueados,

            "erros": erros,

            "fotos_novas": fotos_novas,

            "restantes": restantes,

            "resultado": resultados,

        }



    def salvar_imagens(

        self,

        imovel: Imovel,

        imagens: List[str],

    ) -> List[ImovelImagem]:

        """Salva as imagens encontradas para um imóvel."""



        imagens_salvas = []



        try:

            for ordem, url_img in enumerate(imagens):

                if not url_img:

                    continue



                # Evita duplicar a mesma imagem

                imagem_existente = (

                    self.db.query(ImovelImagem)

                    .filter(

                        ImovelImagem.imovel_id == imovel.id,

                        ImovelImagem.url == url_img,

                    )

                    .first()

                )



                if imagem_existente:

                    imagens_salvas.append(imagem_existente)

                    continue



                nova_imagem = ImovelImagem(

                    imovel_id=imovel.id,

                    url=url_img,

                    ordem=ordem,

                )



                self.db.add(nova_imagem)

                imagens_salvas.append(nova_imagem)



            self.db.commit()



            # Define a primeira foto como imagem principal,

            # caso o imóvel ainda não tenha uma.

            if imagens_salvas and not imovel.url_imagem:

                imovel.url_imagem = imagens_salvas[0].url

                self.db.add(imovel)



            self.db.commit()



            for imagem in imagens_salvas:

                self.db.refresh(imagem)



            return imagens_salvas



        except Exception as e:

            self.db.rollback()

            logger.error(

                f"Erro ao salvar imagens do imóvel {imovel.id}: {e}"

            )

            raise
