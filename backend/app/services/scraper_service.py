import logging
import time

import re
from sqlalchemy import and_, inspect as sa_inspect, not_, or_

from typing import List

from datetime import datetime

from sqlalchemy.orm import Session



from app.models.imovel import Imovel, ImovelImagem, ImovelFotoVerificacao

from app.schemas.imovel_scraper import ImovelScraper

from app.scrapers.caixa import CaixaFalhaTecnicaError, CaixaScraper
from app.services.caixa_datas_worker import reativar_worker_datas_caixa
from app.services.caixa_acesso import intervalo_entre_fotos, registrar_bloqueio_caixa

# Descarga das listas só com requests (sem Selenium); ver caixa_lista_segura.
from app.services.caixa_lista_segura import CaixaListaSegura as CaixaDownloader
from app.services.caixa_datas_edital import PARAGEM_MANUAL

from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.oportunidade import Oportunidade

from app.utils.browser import Browser, CaixaBloqueioError



logger = logging.getLogger(__name__)





class ScraperService:



    def __init__(self, db: Session):

        self.db = db
        self.urls_vistas: set[str] = set()



    def executar_scraper_caixa(self, ufs=None) -> List[Imovel]:

        """Lê os CSV da Caixa e salva/atualiza os imóveis no banco.

        `ufs`: se indicado, só lê os ficheiros dessas UFs (Lista_imoveis_<UF>.csv);
        None lê todos os que estão na pasta (comando manual de importação).
        """

        self.urls_vistas = set()

        scraper = CaixaScraper()
        if ufs is not None:
            scraper.ufs_permitidas = set(ufs)

        dados_imoveis: List[ImovelScraper] = scraper.executar()



        print("DEBUG SCRAPER - QUANTIDADE:", len(dados_imoveis))

        print("DEBUG SCRAPER - PRIMEIROS:", dados_imoveis[:2])



        itens = []

        for imovel_dto in dados_imoveis:
            try:
                itens.append(self._preparar_item(imovel_dto))
            except Exception as e:
                logger.exception(
                    f"ERRO AO SALVAR IMÓVEL {imovel_dto.titulo}: "
                    f"{type(e).__name__}: {e}"
                )

        imoveis_salvos = []

        # Grava em lotes: poucas consultas por lote em vez de várias por imóvel
        # (cada consulta à base remota custa uma ida e volta pela rede).
        # Sem recarregar os objetos a cada commit: nenhuma coluna tem valor
        # gerado pela base além do id, que já fica preenchido.
        expirar_antes = self.db.expire_on_commit
        self.db.expire_on_commit = False
        try:
            for inicio in range(0, len(itens), self.TAMANHO_LOTE_IMPORTACAO):
                lote = itens[inicio:inicio + self.TAMANHO_LOTE_IMPORTACAO]
                try:
                    imoveis_salvos.extend(self._gravar_lote(lote))
                except Exception:
                    self.db.rollback()
                    # Um imóvel com problema não pode impedir os outros: repete
                    # o lote um a um e só perde os que falharem.
                    for item in lote:
                        try:
                            imoveis_salvos.extend(self._gravar_lote([item]))
                        except Exception as e:
                            self.db.rollback()
                            logger.exception(
                                f"ERRO AO SALVAR IMÓVEL {item['dto'].titulo}: "
                                f"{type(e).__name__}: {e}"
                            )
        finally:
            self.db.expire_on_commit = expirar_antes

        return imoveis_salvos

    TAMANHO_LOTE_IMPORTACAO = 200

    def _preparar_item(self, imovel_dto: ImovelScraper) -> dict:
        """Converte o DTO nos campos a gravar e normaliza a URL do imóvel."""
        # 1. Mapeamento explícito de campos (resolve area_util -> area)
        dados_dict = imovel_dto.model_dump(exclude={"imagens", "imagem", "imagem_url"})
        area_valor = dados_dict.pop("area_util", None) or dados_dict.get("area")
        dados_dict["area"] = area_valor
        dados_dict.pop("area_util", None)

        url_imovel = dados_dict.get("url")
        if url_imovel:
            url_texto = str(url_imovel).strip()
            match_id = re.search(r"hdnimovel=([0-9]+)", url_texto, re.IGNORECASE)
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

        urls_imagens = imovel_dto.imagens or []
        if imovel_dto.imagem and imovel_dto.imagem not in urls_imagens:
            urls_imagens.insert(0, imovel_dto.imagem)

        return {"dto": imovel_dto, "dados": dados_dict, "url": url_imovel, "imagens": urls_imagens}

    def _gravar_lote(self, lote: list[dict]) -> List[Imovel]:
        """Grava um lote com um único commit. Em erro levanta a exceção (sem rollback)."""
        # 2. Imóveis já existentes, numa só consulta (o de menor id, se houver repetidos).
        urls = {item["url"] for item in lote if item["url"]}
        por_url: dict[str, Imovel] = {}
        if urls:
            for imovel in (
                self.db.query(Imovel).filter(Imovel.url.in_(urls)).order_by(Imovel.id).all()
            ):
                por_url.setdefault(imovel.url, imovel)

        imagens_existentes: set[tuple[int, str]] = set()
        ids_existentes = [imovel.id for imovel in por_url.values()]
        if ids_existentes and any(item["imagens"] for item in lote):
            imagens_existentes = set(
                self.db.query(ImovelImagem.imovel_id, ImovelImagem.url)
                .filter(ImovelImagem.imovel_id.in_(ids_existentes))
                .all()
            )

        gravados = []
        for item in lote:
            imovel_db = por_url.get(item["url"]) if item["url"] else None
            if imovel_db is not None:
                for chave, valor in item["dados"].items():
                    if valor is not None:
                        setattr(imovel_db, chave, valor)
            else:
                imovel_db = Imovel(**item["dados"])
                self.db.add(imovel_db)
                if item["url"]:
                    por_url[item["url"]] = imovel_db
            gravados.append((imovel_db, item["imagens"]))

        # Um flush para todo o lote: gera os ids dos novos imóveis.
        self.db.flush()

        # 3. Imagens associadas (sem repetir as que já existem)
        com_imagens_novas = []
        for imovel_db, urls_imagens in gravados:
            for ordem, url_img in enumerate(urls_imagens):
                if not url_img or (imovel_db.id, url_img) in imagens_existentes:
                    continue
                imagens_existentes.add((imovel_db.id, url_img))
                self.db.add(ImovelImagem(imovel_id=imovel_db.id, url=url_img, ordem=ordem))
                com_imagens_novas.append(imovel_db)

        self.db.commit()
        for imovel_db in com_imagens_novas:
            # A lista de fotos volta a ser lida da base quando for usada.
            self.db.expire(imovel_db, ["fotos"])

        return [imovel_db for imovel_db, _ in gravados]



    def preparar_fila_fotos_caixa(self, imoveis: List[Imovel]) -> dict:
        """Prepara o status de coleta de fotos dos imÃƒÂ³veis Caixa."""

        pendentes = 0

        com_fotos = 0

        sem_fotos = 0

        # O id sem tocar na base (um objeto expirado por rollback faria um SELECT).
        ids = []
        for imovel in imoveis:
            identidade = sa_inspect(imovel).identity
            if identidade and identidade[0]:
                ids.append(identidade[0])

        # Verificações e "tem fotos" carregadas em blocos, não uma consulta por imóvel.
        verificacoes: dict[int, ImovelFotoVerificacao] = {}
        ids_com_fotos: set[int] = set()
        unicos = list(dict.fromkeys(ids))
        for inicio in range(0, len(unicos), 1000):
            bloco = unicos[inicio:inicio + 1000]
            for verificacao in (
                self.db.query(ImovelFotoVerificacao)
                .filter(ImovelFotoVerificacao.imovel_id.in_(bloco))
                .all()
            ):
                verificacoes.setdefault(verificacao.imovel_id, verificacao)
            ids_com_fotos.update(
                imovel_id for (imovel_id,) in
                self.db.query(ImovelImagem.imovel_id)
                .filter(ImovelImagem.imovel_id.in_(bloco))
                .distinct()
                .all()
            )

        for imovel_id in ids:

            verificacao = verificacoes.get(imovel_id)

            possui_fotos = imovel_id in ids_com_fotos



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

                    imovel_id=imovel_id,

                    resultado=resultado,

                )

                self.db.add(verificacao)
                verificacoes[imovel_id] = verificacao

            elif verificacao.resultado != resultado:

                verificacao.resultado = resultado

                verificacao.verificado_em = datetime.utcnow()



        self.db.commit()



        return {

            "pendentes": pendentes,

            "com_fotos": com_fotos,

            "sem_fotos": sem_fotos,

        }



    # Nunca remove de uma vez mais do que isto (proteção contra listas incompletas).
    LIMITE_REMOCAO_MINIMO = 50
    LIMITE_REMOCAO_FRACAO = 0.05

    def _marcar_descarga_em_curso(self) -> None:
        """Grava (com commit) a paragem manual ANTES de contactar a CAIXA.

        Só é retirada se a descarga terminar sem bloqueio nem exceção: um
        processo que morra a meio deixa todas as rotinas da CAIXA paradas.
        """
        from app.services.caixa_datas_worker import _obter_estado

        estado = _obter_estado(self.db)
        estado.bloqueado_ate = PARAGEM_MANUAL
        estado.atualizado_em = datetime.utcnow()
        self.db.commit()

    def _fechar_descarga(self, download: dict) -> None:
        from app.services.caixa_datas_worker import _obter_estado, registrar_paragem_manual

        estado = _obter_estado(self.db)
        if download.get("bloqueado"):
            registrar_paragem_manual(estado, datetime.utcnow())
            logger.warning(
                "Lista da CAIXA: consultas PARADAS para revisão manual (%s em %s).",
                download.get("paragem") or "bloqueio",
                download.get("uf_bloqueada"),
            )
        else:
            estado.bloqueado_ate = None
            estado.atualizado_em = datetime.utcnow()
        self.db.commit()

    def atualizar_lista_caixa(
        self, max_ufs: int | None = None, remover: bool = True, com_browser: bool = False
    ) -> dict:

        """Baixa, importa e remove anuncios Caixa ausentes da lista atual.

        `max_ufs` limita as UFs descarregadas (comando para a cópia); com menos
        de 27 UFs nada é removido. `remover=False` nunca remove: só conta os
        ausentes (`ausentes_da_lista`), para rever antes de os apagar.
        """



        atualizacao = AtualizacaoCaixa(

            status="EXECUTANDO",

            iniciada_em=datetime.utcnow(),

        )



        self.db.add(atualizacao)

        self.db.commit()

        self.db.refresh(atualizacao)



        try:

            self._marcar_descarga_em_curso()
            if com_browser:
                # Só pelo comando local (scripts/rotina_caixa.py --lista-com-browser).
                from app.services.caixa_downloader import CaixaDownloaderControlado

                baixador = CaixaDownloaderControlado()
            else:
                baixador = CaixaDownloader()
            download = (baixador.baixar_todos(max_ufs=max_ufs) if max_ufs
                        else baixador.baixar_todos())

            # Bloqueio ou resposta inesperada: paragem manual partilhada (todas as
            # rotinas da CAIXA param até revisão); a limpeza não corre (download
            # incompleto).
            self._fechar_descarga(download)

            # Só importa as UFs descarregadas AGORA. Os CSV antigos que ficaram no
            # disco de outras UFs não são lidos: regravavam dados velhos (em
            # 29/10/2026, 26 UFs de 21/10 foram reimportadas depois de um bloqueio).
            ufs_importadas = sorted(set(download.get("sucesso", [])))
            if ufs_importadas:
                imoveis = self.executar_scraper_caixa(ufs=ufs_importadas)
            else:
                logger.warning("Nenhuma UF descarregada nesta execução: nada importado.")
                self.urls_vistas = set()
                imoveis = []



            estados_esperados = set(CaixaDownloader.UFS)

            estados_baixados = set(download.get("sucesso", []))

            urls_ativas = set(self.urls_vistas) | {
                imovel.url
                for imovel in imoveis
                if imovel.url
            }



            removidos = 0
            remocao_recusada = 0
            ausentes_da_lista = None

            # Todas as listas desta descarga têm de ter a mesma data de geração.
            geracoes = download.get("geracoes")
            geracao_unica = geracoes is None or len(set(geracoes.values())) == 1



            # So removemos anuncios quando a lista nacional foi baixada por inteiro.

            # Em uma atualizacao parcial, arquivos ausentes nao podem ser tratados

            # como se os respectivos imoveis tivessem saido da Caixa.

            if estados_baixados == estados_esperados and urls_ativas and geracao_unica:

                ausentes, limite = self._contar_ausentes(urls_ativas)
                ausentes_da_lista = ausentes
                if not remover:
                    logger.info(
                        "Limpeza de imoveis Caixa desligada nesta execucao: %s ausentes "
                        "da lista (nada removido).",
                        ausentes,
                    )
                elif ausentes > limite:
                    remocao_recusada = ausentes
                    logger.warning(
                        "Limpeza de imoveis Caixa RECUSADA: %s ausentes da lista "
                        "(limite %s). Rever manualmente.",
                        ausentes,
                        limite,
                    )
                else:
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

                "ufs_importadas": ufs_importadas,

                "imoveis_atualizados": len(imoveis),

                "imoveis_removidos": removidos,

                "remocao_recusada": remocao_recusada,

                "ausentes_da_lista": ausentes_da_lista,

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


    def _contar_ausentes(self, urls_ativas: set[str]) -> tuple[int, int]:
        """Quantos imóveis Caixa da base faltam na lista e o limite de remoção."""
        urls = [
            url for (url,) in self.db.query(Imovel.url).filter(
                Imovel.fonte.ilike("%caixa%"), Imovel.url.isnot(None)
            )
        ]
        ausentes = sum(1 for url in urls if url not in urls_ativas)
        limite = max(self.LIMITE_REMOCAO_MINIMO, int(len(urls) * self.LIMITE_REMOCAO_FRACAO))
        return ausentes, limite

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
