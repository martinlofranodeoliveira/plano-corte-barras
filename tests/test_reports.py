"""Testes do módulo de relatórios, CSV, Markdown, SVG e ZIP para plano-corte-barras."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from plano_corte_barras.core import otimizar_plano_corte
from plano_corte_barras.errors import ERR_ARQUIVO_EXISTENTE, ErroExecucao
from plano_corte_barras.reports import (
    gerar_csv_plano_corte,
    gerar_csv_resumo_barras,
    gerar_dicionario_resultado,
    gerar_lista_corte_markdown,
    gerar_painel_svg,
    publicar_pacote_zip,
    sanitizar_campo_csv,
)


class TestReports(unittest.TestCase):
    def setUp(self):
        self.dados_base = {
            "projeto": {"nome": "Projeto Serralheria Teste"},
            "parametros": {"espessura_corte_mm": 3, "margem_seguranca_ponta_mm": 5},
            "estoque_barras": [
                {"id": "B1", "perfil": "TUBO", "comprimento_mm": 6000, "quantidade": 2, "custo_unitario_centavos": 12000},
            ],
            "pecas_demandadas": [
                {"id": "=MALICIOSA", "perfil": "TUBO", "comprimento_mm": 2000, "quantidade": 2, "descricao": "+Macro"},
                {"id": "@CMD", "perfil": "TUBO", "comprimento_mm": 1500, "quantidade": 1, "descricao": "-Inject"},
            ],
        }
        self.resultado = otimizar_plano_corte(self.dados_base)

    def test_sanitizacao_formula_injection(self):
        self.assertEqual(sanitizar_campo_csv("=1+1"), "'=1+1")
        self.assertEqual(sanitizar_campo_csv("+SOMAR()"), "'+SOMAR()")
        self.assertEqual(sanitizar_campo_csv("-123"), "'-123")
        self.assertEqual(sanitizar_campo_csv("@cmd"), "'@cmd")
        self.assertEqual(sanitizar_campo_csv("\ttab"), "'\ttab")
        self.assertEqual(sanitizar_campo_csv("Peça Normal"), "Peça Normal")

    def test_geracao_csv_plano_corte(self):
        csv_texto = gerar_csv_plano_corte(self.resultado)
        self.assertIn("indice_barra", csv_texto)
        self.assertIn("posicao_inicio_mm", csv_texto)
        self.assertIn("'=MALICIOSA", csv_texto)  # Sanitizado!
        self.assertIn("'+Macro", csv_texto)      # Sanitizado!
        self.assertIn("'@CMD", csv_texto)        # Sanitizado!

    def test_geracao_csv_resumo_barras(self):
        csv_texto = gerar_csv_resumo_barras(self.resultado)
        self.assertIn("indice_barra", csv_texto)
        self.assertIn("aproveitamento_percentual", csv_texto)
        self.assertIn("custo_formatado", csv_texto)

    def test_geracao_lista_corte_markdown(self):
        md = gerar_lista_corte_markdown(self.resultado)
        self.assertIn("Roteiro de Corte de Oficina — Projeto Serralheria Teste", md)
        self.assertIn("Instruções de Corte Barra a Barra", md)
        self.assertIn("LOFRANO TECNOLOGIA", md)

    def test_geracao_dicionario_resultado(self):
        d = gerar_dicionario_resultado(self.resultado)
        self.assertEqual(d["projeto"]["nome"], "Projeto Serralheria Teste")
        self.assertIn("resumo_global", d)
        self.assertIn("barras_cortadas", d)

    def test_geracao_painel_svg(self):
        svg = gerar_painel_svg(self.resultado)
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.strip().endswith("</svg>"))
        self.assertIn('width="1440"', svg)
        self.assertIn('height="900"', svg)
        self.assertIn("Projeto Serralheria Teste", svg)

    def test_publicar_pacote_zip_sucesso(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho_zip = Path(tmpdir) / "teste.zip"
            arquivos = {
                "plano.csv": b"1,2,3",
                "dados.json": b'{"ok": 1}',
            }
            publicar_pacote_zip(caminho_zip, arquivos)
            self.assertTrue(caminho_zip.exists())

            with zipfile.ZipFile(caminho_zip, "r") as zf:
                self.assertEqual(set(zf.namelist()), {"plano.csv", "dados.json"})

    def test_publicar_pacote_zip_impede_sobrescrita(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho_zip = Path(tmpdir) / "existente.zip"
            caminho_zip.write_bytes(b"ja existe")

            with self.assertRaises(ErroExecucao) as ctx:
                publicar_pacote_zip(caminho_zip, {"a.txt": b"123"})
            self.assertEqual(ctx.exception.codigo, ERR_ARQUIVO_EXISTENTE)


if __name__ == "__main__":
    unittest.main()
