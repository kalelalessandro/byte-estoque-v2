"""Casos do plano V1.4 que não possuem automação de aceitação própria.

Eles entram no cômputo dos 395 casos, mas ficam explicitamente marcados como
``skip`` para não mascarar cobertura. Os dois primeiros são E2E de usuários; os
demais dependem de funcionalidades que o escopo atual de Operações não possui
(status pendente, idempotência de duplo clique e parcelas informadas manualmente).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="E2E/UI: confirmação de exclusão é da tela, não da API.")
def test_usr_n17_cancelar_confirmacao_ao_apagar_funcionario():
    """USR-N17: cancelar a confirmação ao apagar funcionário (E2E)."""


@pytest.mark.skip(reason="E2E/UI: ocultar exclusão do Dono é comportamento da tela.")
def test_usr_n21_lista_nao_mostra_apagar_dono():
    """USR-N21: lista não oferece a opção de apagar o Dono (E2E)."""


@pytest.mark.skip(reason="Escopo atual de Operações não implementa status pendente.")
def test_ope_p13_cancelar_operacao_pendente():
    """OPE-P13: cancelar operação pendente sem alterar estoque."""


@pytest.mark.skip(reason="A API atual registra a operação concluída; não existe endpoint de concluir.")
def test_ope_n12_duplo_clique_nao_aplica_estoque_duas_vezes():
    """OPE-N12: duplo clique em concluir não aplica estoque duas vezes."""


@pytest.mark.skip(reason="Idempotência de conclusão não existe na API atual (operação já nasce concluída).")
def test_con_n02_conclusao_simultanea_nao_aplica_estoque_duas_vezes():
    """CON-N02: conclusões simultâneas da mesma operação."""


@pytest.mark.skip(reason="A API calcula a soma das parcelas; não recebe parcelas manuais com total divergente.")
def test_ope_n16_soma_das_parcelas_diferente_do_total():
    """OPE-N16: soma das parcelas diferente do total."""


@pytest.mark.skip(reason="A API calcula o vencimento das parcelas; não há parcela sem data.")
def test_ope_n17_parcela_sem_vencimento():
    """OPE-N17: parcela sem data de vencimento."""


@pytest.mark.skip(reason="A API divide o total automaticamente; não há parcela de valor zero.")
def test_ope_n18_parcela_valor_zero():
    """OPE-N18: parcela com valor zero."""
