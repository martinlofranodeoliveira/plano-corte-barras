"""Testes unitários e matemáticos do motor de otimização de plano de corte 1D."""

import unittest
from fractions import Fraction

from plano_corte_barras.core import (
    formatar_fracao_percentual,
    formatar_moeda_centavos,
    otimizar_plano_corte,
)
from plano_corte_barras.errors import (
    ERR_COMPRIMENTO_INVALIDO,
    ERR_DEMANDA_VAZIA,
    ERR_ESTOQUE_INSUFICIENTE,
    ERR_ESTOQUE_VAZIO,
    ERR_PARAMETRO_INVALIDO,
    ERR_PECA_MAIOR_QUE_BARRA,
    ERR_PERFIL_INCOMPATIVEL,
    ERR_QUANTIDADE_INVALIDA,
    ERR_VALOR_INVALIDO,
    ErroInviavel,
    ErroValidacaoEntrada,
)


class TestCore(unittest.TestCase):
    def test_formatar_moeda_centavos(self):
        self.assertEqual(formatar_moeda_centavos(0), "R$ 0,00")
        self.assertEqual(formatar_moeda_centavos(150), "R$ 1,50")
        self.assertEqual(formatar_moeda_centavos(14500), "R$ 145,00")
        self.assertEqual(formatar_moeda_centavos(123456789), "R$ 1.234.567,89")
        self.assertEqual(formatar_moeda_centavos(-500), "-R$ 5,00")

    def test_formatar_fracao_percentual(self):
        self.assertEqual(formatar_fracao_percentual(Fraction(1, 2)), "50,00%")
        self.assertEqual(formatar_fracao_percentual(Fraction(3, 4)), "75,00%")
        self.assertEqual(formatar_fracao_percentual(Fraction(1, 3)), "33,33%")
        self.assertEqual(formatar_fracao_percentual(Fraction(2, 3)), "66,67%")
        self.assertEqual(formatar_fracao_percentual(Fraction(9876, 10000)), "98,76%")

    def test_encaixe_exato_sem_sobra(self):
        # 1 barra de 6000 mm, kerf 0, 2 peças de 3000 mm
        dados = {
            "projeto": {"nome": "Teste Encaixe Perfeito"},
            "parametros": {"espessura_corte_mm": 0, "margem_seguranca_ponta_mm": 0},
            "estoque_barras": [{"id": "B1", "perfil": "TUBO", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "perfil": "TUBO", "comprimento_mm": 3000, "quantidade": 2}],
        }
        res = otimizar_plano_corte(dados)
        self.assertEqual(len(res.barras_cortadas), 1)
        b = res.barras_cortadas[0]
        self.assertEqual(len(b.pecas), 2)
        self.assertEqual(b.sobra_final_mm, 0)
        self.assertEqual(b.taxa_aproveitamento, Fraction(1, 1))
        self.assertEqual(res.resumo_global.aproveitamento_global_percentual, "100,00%")

    def test_conservacao_milimetrica_com_kerf_e_margem(self):
        # Barra 6000 mm, margem ponta 10 mm, kerf 5 mm
        # P1 = 2000 mm, P2 = 2500 mm. Pela ordenação decrescente (FFD), P2 (2500 mm) é cortada primeiro.
        # P2: inicio=10, fim=2510, perda_kerf=5
        # P1: inicio=2515, fim=4515, perda_kerf=5 (pois há sobra após P1)
        # Sobra final = 6000 - 4520 = 1480 mm
        dados = {
            "parametros": {"espessura_corte_mm": 5, "margem_seguranca_ponta_mm": 10, "comprimento_minimo_aproveitavel_mm": 500},
            "estoque_barras": [{"id": "B1", "perfil": "PERFIL_U", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [
                {"id": "P1", "perfil": "PERFIL_U", "comprimento_mm": 2000, "quantidade": 1},
                {"id": "P2", "perfil": "PERFIL_U", "comprimento_mm": 2500, "quantidade": 1},
            ],
        }
        res = otimizar_plano_corte(dados)
        b = res.barras_cortadas[0]
        self.assertEqual(b.refugo_ponta_mm, 10)
        self.assertEqual(b.pecas[0].comprimento_mm, 2500)
        self.assertEqual(b.pecas[0].posicao_inicio_mm, 10)
        self.assertEqual(b.pecas[0].posicao_fim_mm, 2510)
        self.assertEqual(b.pecas[0].perda_corte_mm, 5)

        self.assertEqual(b.pecas[1].comprimento_mm, 2000)
        self.assertEqual(b.pecas[1].posicao_inicio_mm, 2515)
        self.assertEqual(b.pecas[1].posicao_fim_mm, 4515)
        self.assertEqual(b.pecas[1].perda_corte_mm, 5)

        self.assertEqual(b.sobra_final_mm, 1480)
        self.assertEqual(b.tipo_sobra, "APROVEITAVEL")  # 1480 >= 500

        # Identidade de conservação estrita
        total_verificado = 10 + (2500 + 5) + (2000 + 5) + 1480
        self.assertEqual(total_verificado, 6000)

    def test_classificacao_sobra_sucata_vs_aproveitavel(self):
        # Sobra menor que limiar vira sucata
        dados = {
            "parametros": {"espessura_corte_mm": 0, "margem_seguranca_ponta_mm": 0, "comprimento_minimo_aproveitavel_mm": 1000},
            "estoque_barras": [{"id": "B1", "perfil": "P", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "perfil": "P", "comprimento_mm": 5500, "quantidade": 1}],
        }
        res = otimizar_plano_corte(dados)
        b = res.barras_cortadas[0]
        self.assertEqual(b.sobra_final_mm, 500)
        self.assertEqual(b.tipo_sobra, "SUCATA")
        self.assertEqual(res.resumo_global.total_sucata_descarte_mm, 500)
        self.assertEqual(res.resumo_global.total_sobra_aproveitavel_mm, 0)

    def test_multiplos_perfis_independentes(self):
        dados = {
            "estoque_barras": [
                {"id": "B_ACO", "perfil": "ACO", "comprimento_mm": 6000, "quantidade": 5},
                {"id": "B_ALU", "perfil": "ALUMINIO", "comprimento_mm": 4000, "quantidade": 5},
            ],
            "pecas_demandadas": [
                {"id": "P_ACO", "perfil": "ACO", "comprimento_mm": 1900, "quantidade": 3},
                {"id": "P_ALU", "perfil": "ALUMINIO", "comprimento_mm": 1500, "quantidade": 2},
            ],
        }
        res = otimizar_plano_corte(dados)
        perfis_usados = set(b.perfil for b in res.barras_cortadas)
        self.assertEqual(perfis_usados, {"ACO", "ALUMINIO"})
        self.assertEqual(len(res.barras_cortadas), 2)  # 1 de aço (1900*3 + 2*3 = 5706 <= 6000) e 1 de alumínio (1500*2 + 3 = 3003 <= 4000)

    def test_rejeicao_peca_maior_que_barra_disponivel(self):
        dados = {
            "estoque_barras": [{"id": "B1", "perfil": "P", "comprimento_mm": 6000, "quantidade": 2}],
            "pecas_demandadas": [{"id": "P1", "perfil": "P", "comprimento_mm": 6500, "quantidade": 1}],
        }
        with self.assertRaises(ErroInviavel) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_PECA_MAIOR_QUE_BARRA)

    def test_rejeicao_peca_maior_com_margem_seguranca(self):
        # Barra 6000 mm, margem ponta 50 mm -> útil 5950 mm. Peça 5980 mm não cabe!
        dados = {
            "parametros": {"margem_seguranca_ponta_mm": 50},
            "estoque_barras": [{"id": "B1", "perfil": "P", "comprimento_mm": 6000, "quantidade": 2}],
            "pecas_demandadas": [{"id": "P1", "perfil": "P", "comprimento_mm": 5980, "quantidade": 1}],
        }
        with self.assertRaises(ErroInviavel) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_PECA_MAIOR_QUE_BARRA)

    def test_rejeicao_estoque_insuficiente(self):
        dados = {
            "estoque_barras": [{"id": "B1", "perfil": "P", "comprimento_mm": 3000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "perfil": "P", "comprimento_mm": 2000, "quantidade": 2}],
        }
        with self.assertRaises(ErroInviavel) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_ESTOQUE_INSUFICIENTE)

    def test_rejeicao_perfil_inexistente_no_estoque(self):
        dados = {
            "estoque_barras": [{"id": "B1", "perfil": "TUBO_FERRO", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "perfil": "CANTONEIRA_INOX", "comprimento_mm": 2000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_PERFIL_INCOMPATIVEL)

    def test_rejeicao_estoque_vazio(self):
        dados = {
            "estoque_barras": [],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": 2000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_ESTOQUE_VAZIO)

    def test_rejeicao_demanda_vazia(self):
        dados = {
            "estoque_barras": [{"id": "B1", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_DEMANDA_VAZIA)

    def test_rejeicao_comprimento_negativo_barra(self):
        dados = {
            "estoque_barras": [{"id": "B1", "comprimento_mm": -6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": 1000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_COMPRIMENTO_INVALIDO)

    def test_rejeicao_comprimento_negativo_peca(self):
        dados = {
            "estoque_barras": [{"id": "B1", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": -1000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_COMPRIMENTO_INVALIDO)

    def test_rejeicao_parametro_kerf_negativo(self):
        dados = {
            "parametros": {"espessura_corte_mm": -3},
            "estoque_barras": [{"id": "B1", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": 1000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_PARAMETRO_INVALIDO)

    def test_escala_cem_pecas_pequenas(self):
        # 100 peças de 500 mm em barras de 6000 mm, kerf 3 mm
        # Em 6000 mm cabem 11 peças: 11*500 + 11*3 = 5533 mm.
        # Precisaremos de ceil(100/11) = 10 barras.
        dados = {
            "parametros": {"espessura_corte_mm": 3, "margem_seguranca_ponta_mm": 0},
            "estoque_barras": [{"id": "B6M", "perfil": "TUBO", "comprimento_mm": 6000, "quantidade": 20}],
            "pecas_demandadas": [{"id": "P500", "perfil": "TUBO", "comprimento_mm": 500, "quantidade": 100}],
        }
        res = otimizar_plano_corte(dados)
        self.assertEqual(res.resumo_global.total_barras_utilizadas, 10)
        self.assertEqual(sum(len(b.pecas) for b in res.barras_cortadas), 100)

    def test_multiplos_comprimentos_de_barra_no_estoque(self):
        # Estoque com barras de 6000 mm e barras de 3000 mm
        # Peça de 2800 mm deve preferir a barra de 3000 mm (menor sobra)
        dados = {
            "parametros": {"espessura_corte_mm": 0, "margem_seguranca_ponta_mm": 0},
            "estoque_barras": [
                {"id": "B6M", "perfil": "TUBO", "comprimento_mm": 6000, "quantidade": 5},
                {"id": "B3M", "perfil": "TUBO", "comprimento_mm": 3000, "quantidade": 5},
            ],
            "pecas_demandadas": [{"id": "P2800", "perfil": "TUBO", "comprimento_mm": 2800, "quantidade": 1}],
        }
        res = otimizar_plano_corte(dados)
        self.assertEqual(len(res.barras_cortadas), 1)
        self.assertEqual(res.barras_cortadas[0].barra_estoque_id, "B3M")
        self.assertEqual(res.barras_cortadas[0].sobra_final_mm, 200)

    def test_sobra_exatamente_igual_ao_limiar_e_aproveitavel(self):
        dados = {
            "parametros": {"espessura_corte_mm": 0, "margem_seguranca_ponta_mm": 0, "comprimento_minimo_aproveitavel_mm": 500},
            "estoque_barras": [{"id": "B1", "perfil": "P", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "perfil": "P", "comprimento_mm": 5500, "quantidade": 1}],
        }
        res = otimizar_plano_corte(dados)
        self.assertEqual(res.barras_cortadas[0].sobra_final_mm, 500)
        self.assertEqual(res.barras_cortadas[0].tipo_sobra, "APROVEITAVEL")

    def test_corte_oxicorte_kerf_largo_20mm(self):
        # Kerf de maçarico / plasma de 20 mm
        dados = {
            "parametros": {"espessura_corte_mm": 20, "margem_seguranca_ponta_mm": 50},
            "estoque_barras": [{"id": "B1", "perfil": "CHAPA", "comprimento_mm": 3000, "quantidade": 1}],
            "pecas_demandadas": [
                {"id": "P1", "perfil": "CHAPA", "comprimento_mm": 1000, "quantidade": 2},
            ],
        }
        res = otimizar_plano_corte(dados)
        b = res.barras_cortadas[0]
        # 50 (ponta) + 1000 + 20 (kerf) + 1000 + 20 (kerf) = 2090
        # Sobra = 3000 - 2090 = 910 mm
        self.assertEqual(b.sobra_final_mm, 910)
        self.assertEqual(b.refugo_ponta_mm, 50)
        self.assertEqual(b.perda_cortes_total_mm, 40)

    def test_rejeicao_quantidade_zero_ou_negativa_estoque(self):
        dados = {
            "estoque_barras": [{"id": "B1", "comprimento_mm": 6000, "quantidade": 0}],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": 1000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_QUANTIDADE_INVALIDA)

    def test_rejeicao_quantidade_zero_ou_negativa_demanda(self):
        dados = {
            "estoque_barras": [{"id": "B1", "comprimento_mm": 6000, "quantidade": 5}],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": 1000, "quantidade": -2}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_QUANTIDADE_INVALIDA)

    def test_rejeicao_custo_negativo_barra(self):
        dados = {
            "estoque_barras": [{"id": "B1", "comprimento_mm": 6000, "quantidade": 1, "custo_unitario_centavos": -100}],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": 1000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_VALOR_INVALIDO)

    def test_rejeicao_dados_raiz_nao_dicionario(self):
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(["invalido"])  # type: ignore
        self.assertEqual(ctx.exception.codigo, ERR_VALOR_INVALIDO)

    def test_rejeicao_margem_seguranca_negativa(self):
        dados = {
            "parametros": {"margem_seguranca_ponta_mm": -10},
            "estoque_barras": [{"id": "B1", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": 1000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_PARAMETRO_INVALIDO)

    def test_rejeicao_limiar_sobra_negativo(self):
        dados = {
            "parametros": {"comprimento_minimo_aproveitavel_mm": -50},
            "estoque_barras": [{"id": "B1", "comprimento_mm": 6000, "quantidade": 1}],
            "pecas_demandadas": [{"id": "P1", "comprimento_mm": 1000, "quantidade": 1}],
        }
        with self.assertRaises(ErroValidacaoEntrada) as ctx:
            otimizar_plano_corte(dados)
        self.assertEqual(ctx.exception.codigo, ERR_PARAMETRO_INVALIDO)


if __name__ == "__main__":
    unittest.main()
