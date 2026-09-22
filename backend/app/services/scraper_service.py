import logging
import re
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.imovel import Imovel, ImovelImagem, ImovelFotoVerificacao
from app.schemas.imovel_scraper import ImovelScraper
from app.scrapers.caixa import CaixaScraper
from app.services.caixa_downloader import CaixaDownloader
from app.utils.browser import Browser, CaixaBloqueioError

logger = logging.getLogger(__name__)


class ScraperService:

    def __init__(self, db: Session):
        self.db = db

    def executar_scraper_caixa(self) -> List[Imovel]:
        """Executa o scraper da Caixa e salva/atualiza os imÃƒÂ³veis no banco."""
        scraper = CaixaScraper()
        dados_imoveis: List[ImovelScraper] = scraper.executar()

        print("DEBUG SCRAPER - QUANTIDADE:", len(dados_imoveis))
        print("DEBUG SCRAPER - PRIMEIROS:", dados_imoveis[:2])

        imoveis_salvos = []

        for imovel_dto in dados_imoveis:
            try:
                # 1. Mapeamento explÃƒÂ­cito de campos (resolve area_util -> area)
                dados_dict = imovel_dto.model_dump(
                    exclude={"imagens", "imagem", "imagem_url"}
                )

                # Trata equivalÃƒÂªncia de ÃƒÂ¡rea
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


                # 2. Verifica se o imÃƒÂ³vel jÃƒÂ¡ existe no banco (via URL ou Titulo/Endereco)
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
                    f"ERRO AO SALVAR IMÃƒâ€œVEL {imovel_dto.titulo}: "
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
        """Baixa, importa e remove anÃƒÂºncios Caixa ausentes da lista atual."""
        download = CaixaDownloader().baixar_todos()
        imoveis = self.executar_scraper_caixa()

        estados_esperados = set(CaixaDownloader.UFS)
        estados_baixados = set(download.get("sucesso", []))
        urls_ativas = {imovel.url for imovel in imoveis if imovel.url}
        removidos = 0

        # SÃƒÂ³ removemos anÃƒÂºncios quando a lista nacional foi baixada por inteiro.
        # Em uma atualizaÃƒÂ§ÃƒÂ£o parcial, arquivos ausentes nÃƒÂ£o podem ser tratados
        # como se os respectivos imÃƒÂ³veis tivessem saÃƒÂ­do da Caixa.
        if estados_baixados == estados_esperados and urls_ativas:
            removidos = self._remover_imoveis_caixa_inativos(urls_ativas)
        else:
            logger.warning(
                "Limpeza de imÃƒÂ³veis Caixa ignorada: download incompleto ou sem URLs."
            )

        fila_fotos = self.preparar_fila_fotos_caixa(imoveis)

        return {
            "download": download,
            "imoveis_atualizados": len(imoveis),
            "imoveis_removidos": removidos,
            "fila_fotos": fila_fotos,
        }

    def _remover_imoveis_caixa_inativos(self, urls_ativas: set[str]) -> int:
        """Remove do banco somente anÃƒÂºncios Caixa ausentes da lista vigente."""

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

        for imovel in inativos:
            # Remove verificaÃƒÂ§ÃƒÂµes de fotos vinculadas ao imÃƒÂ³vel.
            self.db.query(ImovelFotoVerificacao).filter(
                ImovelFotoVerificacao.imovel_id == imovel.id
            ).delete(synchronize_session=False)

            # Remove imagens vinculadas ao imÃƒÂ³vel.
            self.db.query(ImovelImagem).filter(
                ImovelImagem.imovel_id == imovel.id
            ).delete(synchronize_session=False)

            # SÃƒÂ³ entÃƒÂ£o remove o imÃƒÂ³vel.
            self.db.delete(imovel)

        if inativos:
            self.db.commit()

        return len(inativos)

    def processar_fila_fotos_caixa(
        self,
        limite: int = 10,
    ) -> dict:
        """Processa imÃƒÂ³veis Caixa pendentes de coleta de fotos."""

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

            for imovel in pendentes:
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

                    # NÃƒÂ£o continuar fazendo requisiÃƒÂ§ÃƒÂµes
                    # depois que a Caixa bloqueou.
                    break

                except Exception as exc:
                    verificacao.resultado = "PENDENTE"
                    verificacao.verificado_em = datetime.utcnow()
                    self.db.commit()

                    erros += 1

                    logger.error(
                        f"Erro ao coletar fotos do imÃƒÂ³vel "
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
        """Salva as imagens encontradas para um imÃƒÂ³vel."""

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
            # caso o imÃƒÂ³vel ainda nÃƒÂ£o tenha uma.
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
                f"Erro ao salvar imagens do imÃƒÂ³vel {imovel.id}: {e}"
            )
            raise
