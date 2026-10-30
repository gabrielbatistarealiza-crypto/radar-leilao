from app.models.usuario import Usuario
from app.models.corretor import Corretor
from app.models.imovel import Imovel, ImovelEvento, ImovelImagem, ImovelFotoVerificacao
from app.models.atualizacao_caixa import AtualizacaoCaixa
from app.models.oportunidade import Oportunidade
from app.models.negociacao import Negociacao
from app.models.operacao import Operacao
from app.models.anuncio_imovel import AnuncioImovel
from app.models.anuncio_imagem import AnuncioImagem
from app.models.atividade_oportunidade import AtividadeOportunidade
from app.models.criterio_alerta import CriterioAlerta
from app.models.caixa_data_worker_state import CaixaDataWorkerState
from app.models.caixa_pedidos_dia import CaixaPedidosDia
# Todos os modelos têm de estar aqui: o Alembic e o create_all só conhecem as
# tabelas importadas (o teste test_migracoes verifica que não falta nenhuma).
from app.models.notificacao import Notificacao
from app.models.simulacao_rentabilidade import SimulacaoRentabilidade
from app.models.pedido_corretor import PedidoCorretor
from app.models.recuperacao_senha import RecuperacaoSenha
