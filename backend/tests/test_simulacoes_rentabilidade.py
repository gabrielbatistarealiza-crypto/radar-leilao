from datetime import datetime
from decimal import Decimal
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError

from app.models.simulacao_rentabilidade import SimulacaoRentabilidade
from app.routers.simulacoes_rentabilidade import (
    SimulacaoCreate,
    montar_resposta,
    obter_oportunidade,
)


class SimulacoesRentabilidadeTest(unittest.TestCase):
    def test_calcula_custo_lucro_margem_e_roi_com_custos_informados(self):
        simulacao = SimulacaoRentabilidade(
            id=1,
            oportunidade_id=4,
            nome="Reforma básica",
            preco_aquisicao=Decimal("200000.00"),
            impostos_taxas=Decimal("10000.00"),
            custos_juridicos=Decimal("5000.00"),
            reformas=Decimal("25000.00"),
            outras_despesas=Decimal("5000.00"),
            valor_revenda=Decimal("300000.00"),
            observacoes=None,
            criado_por_id=7,
            criado_em=datetime(2026, 1, 1),
        )
        resultado = montar_resposta(simulacao)
        self.assertEqual(resultado["custo_total"], Decimal("245000.00"))
        self.assertEqual(resultado["lucro_estimado"], Decimal("55000.00"))
        self.assertEqual(resultado["margem_revenda"], Decimal("18.33333333333333333333333333"))
        self.assertEqual(resultado["roi"], Decimal("22.44897959183673469387755102"))
        self.assertEqual(resultado["custos_nao_informados"], [])

    def test_custos_ausentes_sao_marcados_e_tratados_como_zero(self):
        simulacao = SimulacaoRentabilidade(
            id=1,
            oportunidade_id=4,
            nome="Inicial",
            preco_aquisicao=Decimal("100000"),
            valor_revenda=Decimal("120000"),
            criado_em=datetime(2026, 1, 1),
        )
        resultado = montar_resposta(simulacao)
        self.assertEqual(resultado["custo_total"], Decimal("100000"))
        self.assertEqual(resultado["lucro_estimado"], Decimal("20000"))
        self.assertEqual(resultado["custos_nao_informados"], [
            "Impostos e taxas", "Custos jurídicos", "Reformas", "Outras despesas"
        ])

    def test_preco_nao_pode_ser_negativo(self):
        with self.assertRaises(ValidationError):
            SimulacaoCreate(nome="Inválido", preco_aquisicao=-1, valor_revenda=100)

    def test_acesso_restrito_a_cliente_corretor_atribuido_e_admin(self):
        oportunidade = SimpleNamespace(id=8, cliente_id=9, corretor_id=12)

        class Consulta:
            def filter(self, *_):
                return self

            def first(self):
                return oportunidade

        class Banco:
            def query(self, *_):
                return Consulta()

        self.assertIs(obter_oportunidade(Banco(), 8, SimpleNamespace(id=12, tipo="corretor", admin=False)), oportunidade)
        self.assertIs(obter_oportunidade(Banco(), 8, SimpleNamespace(id=9, tipo="cliente", admin=False)), oportunidade)
        self.assertIs(obter_oportunidade(Banco(), 8, SimpleNamespace(id=90, tipo="admin", admin=True)), oportunidade)
        with self.assertRaises(HTTPException) as erro:
            obter_oportunidade(Banco(), 8, SimpleNamespace(id=13, tipo="corretor", admin=False))
        self.assertEqual(erro.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
