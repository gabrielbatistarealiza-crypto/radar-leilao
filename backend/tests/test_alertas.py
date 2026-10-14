from datetime import date, timedelta
from decimal import Decimal
import unittest
from unittest.mock import MagicMock
import uuid
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.models.anuncio_imagem import AnuncioImagem
from app.models.anuncio_imovel import AnuncioImovel
from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.atividade_oportunidade import AtividadeOportunidade
from app.models.corretor import Corretor
from app.models.imovel import Imovel, ImovelFotoVerificacao, ImovelImagem
from app.models.criterio_alerta import CriterioAlerta
from app.models.notificacao import Notificacao
from app.models.negociacao import Negociacao
from app.models.oportunidade import Oportunidade
from app.models.operacao import Operacao
from app.models.simulacao_rentabilidade import SimulacaoRentabilidade
from app.models.usuario import Usuario

from app.routers.alertas import (
    CriterioAlertaInput, _acessar_cenario, _desconto, _dias_ate,
    atualizar_alerta, criar_alerta, excluir_alerta, listar_alertas,
    listar_notificacoes, marcar_notificacao_lida,
)
from app.services.notificacoes import (
    gerar_notificacoes,
    libertar_lock_scheduler_notificacoes,
    tentar_lock_scheduler_notificacoes,
)


class AlertasTest(unittest.TestCase):
    def test_roi_exige_cenario_guardado(self):
        with self.assertRaises(ValidationError):
            CriterioAlertaInput(nome="ROI", roi_minimo=15)

    def test_criterio_roi_com_cenario_e_valido(self):
        criterio = CriterioAlertaInput(nome="ROI", roi_minimo=15, simulacao_id=4)
        self.assertEqual(criterio.simulacao_id, 4)

    def test_desconto_recalculado_a_partir_de_avaliacao_e_lance(self):
        imovel = SimpleNamespace(valor_avaliacao=Decimal("200000"), valor_leilao=Decimal("140000"))
        self.assertEqual(_desconto(imovel), Decimal("30.0"))

    def test_desconto_indisponivel_sem_valores_confiaveis(self):
        imovel = SimpleNamespace(valor_avaliacao=None, valor_leilao=100)
        self.assertIsNone(_desconto(imovel))

    def test_prazo_calculado_em_dias_e_datas_passadas_ignoradas_no_alerta(self):
        self.assertEqual(_dias_ate(date.today() + timedelta(days=3)), 3)
        self.assertEqual(_dias_ate(date.today() - timedelta(days=1)), -1)
        self.assertIsNone(_dias_ate(None))

    def test_cenario_com_custos_em_aberto_nao_pode_definir_roi_minimo(self):
        simulacao = SimpleNamespace(
            oportunidade_id=5, impostos_taxas=None, custos_juridicos=0,
            reformas=0, outras_despesas=0,
        )
        oportunidade = SimpleNamespace(id=5, cliente_id=7, corretor_id=None)

        class Consulta:
            def __init__(self, resultado):
                self.resultado = resultado

            def filter(self, *_):
                return self

            def first(self):
                return self.resultado

        class Banco:
            def query(self, modelo):
                return Consulta(simulacao if modelo is SimulacaoRentabilidade else oportunidade)

        with self.assertRaises(HTTPException) as erro:
            _acessar_cenario(Banco(), 2, SimpleNamespace(id=7, tipo="cliente", admin=False))
        self.assertEqual(erro.exception.status_code, 422)


class AlertasPersistenciaTest(unittest.TestCase):
    """Exercita os handlers contra uma base SQLAlchemy real e isolada."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine, autoflush=False)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def setUp(self):
        self.db = self.Session()
        self.db.query(Notificacao).delete(synchronize_session=False)
        self.db.query(CriterioAlerta).delete(synchronize_session=False)
        self.db.commit()
        identificador = uuid.uuid4().hex
        self.dono = Usuario(nome="Cliente", email=f"cliente-{identificador}@example.test", senha="x", tipo="cliente", admin=False)
        self.outro = Usuario(nome="Outro", email=f"outro-{identificador}@example.test", senha="x", tipo="cliente", admin=False)
        self.db.add_all([self.dono, self.outro])
        self.db.flush()
        self.imovel = Imovel(titulo="Casa teste", cidade="Recife", estado="PE")
        self.db.add(self.imovel)
        self.db.flush()
        self.oportunidade = Oportunidade(imovel_id=self.imovel.id, cliente_id=self.dono.id)
        self.db.add(self.oportunidade)
        self.db.flush()
        self.cenario = SimulacaoRentabilidade(
            oportunidade_id=self.oportunidade.id,
            nome="Cenário completo", preco_aquisicao=100000,
            impostos_taxas=0, custos_juridicos=0, reformas=0,
            outras_despesas=0, valor_revenda=120000,
        )
        self.db.add(self.cenario)
        self.db.commit()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_criar_listar_editar_e_excluir_persistem_no_banco(self):
        criterio = criar_alerta(
            CriterioAlertaInput(nome="   Recife   ", estado="PE", alertar_prazos_dias=5),
            self.db, self.dono,
        )
        criterio_id = criterio.id
        usuario_id = self.dono.id
        cenario_id = self.cenario.id
        self.db.expunge_all()
        salvo = listar_alertas(self.db, self.db.get(Usuario, usuario_id))
        self.assertEqual(len(salvo), 1)
        self.assertEqual(salvo[0].nome, "Recife")

        atualizado = atualizar_alerta(
            criterio_id,
            CriterioAlertaInput(nome="Recife e ROI", cidade="Olinda", roi_minimo=10, simulacao_id=cenario_id),
            self.db, self.dono,
        )
        self.db.expunge_all()
        recarregado = self.db.query(type(atualizado)).filter_by(id=criterio_id).one()
        self.assertEqual(recarregado.nome, "Recife e ROI")
        self.assertEqual(recarregado.cidade, "Olinda")
        self.assertEqual(recarregado.simulacao_id, cenario_id)
        self.assertEqual(recarregado.roi_minimo, Decimal("10.00"))

        excluir_alerta(criterio_id, self.db, self.dono)
        self.assertEqual(listar_alertas(self.db, self.dono), [])

    def test_usuario_nao_pode_editar_ou_excluir_criterio_alheio(self):
        criterio = criar_alerta(CriterioAlertaInput(nome="Privado"), self.db, self.dono)
        for operacao in (
            lambda: atualizar_alerta(criterio.id, CriterioAlertaInput(nome="Invadido"), self.db, self.outro),
            lambda: excluir_alerta(criterio.id, self.db, self.outro),
        ):
            with self.subTest(operacao=operacao), self.assertRaises(HTTPException) as erro:
                operacao()
            self.assertEqual(erro.exception.status_code, 404)
        self.db.refresh(criterio)
        self.assertEqual(criterio.nome, "Privado")

    def test_cliente_nao_pode_usar_cenario_de_oportunidade_alheia(self):
        with self.assertRaises(HTTPException) as erro:
            _acessar_cenario(self.db, self.cenario.id, self.outro)
        self.assertEqual(erro.exception.status_code, 403)

    def test_edicao_nao_aceita_cenario_alheio_nem_custos_incompletos(self):
        criterio = criar_alerta(CriterioAlertaInput(nome="Original"), self.db, self.dono)
        oportunidade_alheia = Oportunidade(cliente_id=self.outro.id)
        self.db.add(oportunidade_alheia)
        self.db.flush()
        cenario_alheio = SimulacaoRentabilidade(
            oportunidade_id=oportunidade_alheia.id, nome="Privado",
            preco_aquisicao=100000, impostos_taxas=0, custos_juridicos=0,
            reformas=0, outras_despesas=0, valor_revenda=120000,
        )
        cenario_incompleto = SimulacaoRentabilidade(
            oportunidade_id=self.oportunidade.id, nome="Incompleto",
            preco_aquisicao=100000, valor_revenda=120000,
        )
        self.db.add_all([cenario_alheio, cenario_incompleto])
        self.db.commit()

        for simulacao_id, status in (
            (cenario_alheio.id, 403),
            (cenario_incompleto.id, 422),
        ):
            with self.subTest(simulacao_id=simulacao_id), self.assertRaises(HTTPException) as erro:
                atualizar_alerta(
                    criterio.id,
                    CriterioAlertaInput(nome="Alterado", roi_minimo=10, simulacao_id=simulacao_id),
                    self.db, self.dono,
                )
            self.assertEqual(erro.exception.status_code, status)
            self.db.rollback()
        self.db.refresh(criterio)
        self.assertEqual(criterio.nome, "Original")

    def test_nova_correspondencia_cria_notificacao_deduplicada_e_prazo(self):
        self.imovel.valor_avaliacao = 200000
        self.imovel.valor_leilao = 100000
        self.imovel.data_primeiro_leilao = date.today() + timedelta(days=2)
        self.db.add_all([
            CriterioAlerta(usuario_id=self.dono.id, nome="Desconto", desconto_minimo=20, alertar_prazos_dias=7),
            CriterioAlerta(usuario_id=self.dono.id, nome="Outro critério", preco_maximo=150000, alertar_prazos_dias=7),
        ])
        self.db.commit()

        self.assertEqual(gerar_notificacoes(self.db), 2)
        self.assertEqual(gerar_notificacoes(self.db), 0)
        notificacoes = listar_notificacoes(self.db, self.dono)
        self.assertEqual(len(notificacoes), 2)
        self.assertEqual({item.tipo for item in notificacoes}, {"oportunidade", "prazo"})

    def test_prazo_fora_da_janela_nao_notifica(self):
        self.imovel.data_primeiro_leilao = date.today() + timedelta(days=3)
        self.db.add(CriterioAlerta(usuario_id=self.dono.id, nome="Prazo curto", alertar_prazos_dias=2))
        self.db.commit()

        gerar_notificacoes(self.db)
        self.assertEqual(
            self.db.query(Notificacao).filter_by(usuario_id=self.dono.id, imovel_id=self.imovel.id).count(),
            0,
        )

    def test_historico_e_marcar_como_lida_sao_privados(self):
        notificacao = Notificacao(
            usuario_id=self.dono.id, imovel_id=self.imovel.id,
            evento="correspondencia", tipo="oportunidade",
            titulo="Compatível", mensagem="Casa teste corresponde.",
        )
        self.db.add(notificacao)
        self.db.commit()

        self.assertEqual(listar_notificacoes(self.db, self.outro), [])
        with self.assertRaises(HTTPException) as erro:
            marcar_notificacao_lida(notificacao.id, self.db, self.outro)
        self.assertEqual(erro.exception.status_code, 404)

        marcada = marcar_notificacao_lida(notificacao.id, self.db, self.dono)
        self.assertTrue(marcada.lida)
        self.assertTrue(listar_notificacoes(self.db, self.dono)[0].lida)

    def test_scheduler_lock_e_noop_para_banco_de_teste_nao_postgresql(self):
        # SQLite continua a permitir os testes locais; em produção PostgreSQL
        # a eleição é feita pelo lock de sessão do próprio servidor.
        self.assertTrue(tentar_lock_scheduler_notificacoes(self.db))
        libertar_lock_scheduler_notificacoes(self.db)

    def test_scheduler_lock_postgresql_e_liberado_na_sessao(self):
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "postgresql"
        db.execute.return_value.scalar.return_value = True

        self.assertTrue(tentar_lock_scheduler_notificacoes(db))
        db.commit.assert_called_once()
        libertar_lock_scheduler_notificacoes(db)
        self.assertEqual(db.execute.call_count, 2)

    def test_scheduler_worker_secundario_nao_adquire_lock(self):
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "postgresql"
        db.execute.return_value.scalar.return_value = False

        self.assertFalse(tentar_lock_scheduler_notificacoes(db))
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
