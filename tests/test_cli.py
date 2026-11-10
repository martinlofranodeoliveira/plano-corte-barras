"""Testes da interface de linha de comando (CLI) para plano-corte-barras."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from plano_corte_barras.cli import main


class TestCLI(unittest.TestCase):
    def test_cli_versao(self):
        f = io.StringIO()
        with patch("sys.argv", ["plano-corte-barras", "versao"]):
            with redirect_stdout(f):
                codigo = main()
        self.assertEqual(codigo, 0)
        self.assertIn("plano-corte-barras 1.0.0", f.getvalue())

    def test_cli_exemplo_stdout(self):
        f = io.StringIO()
        with patch("sys.argv", ["plano-corte-barras", "exemplo"]):
            with redirect_stdout(f):
                codigo = main()
        self.assertEqual(codigo, 0)
        dados = json.loads(f.getvalue())
        self.assertIn("estoque_barras", dados)
        self.assertIn("pecas_demandadas", dados)

    def test_cli_exemplo_arquivo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            arq_saida = Path(tmpdir) / "exemplo.json"
            with patch("sys.argv", ["plano-corte-barras", "exemplo", "--saida", str(arq_saida)]):
                with redirect_stdout(io.StringIO()):
                    codigo = main()
            self.assertEqual(codigo, 0)
            self.assertTrue(arq_saida.exists())
            dados = json.loads(arq_saida.read_text(encoding="utf-8"))
            self.assertIn("projeto", dados)

    def test_cli_verificar_sucesso(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            arq_in = Path(tmpdir) / "in.json"
            with patch("sys.argv", ["plano-corte-barras", "exemplo", "-o", str(arq_in)]):
                main()

            f = io.StringIO()
            with patch("sys.argv", ["plano-corte-barras", "verificar", "-i", str(arq_in)]):
                with redirect_stdout(f):
                    codigo = main()
            self.assertEqual(codigo, 0)
            self.assertIn("Entrada válida e viável para corte", f.getvalue())

    def test_cli_verificar_arquivo_inexistente(self):
        f_err = io.StringIO()
        with patch("sys.argv", ["plano-corte-barras", "verificar", "-i", "/tmp/inexistente_corte_123.json"]):
            with redirect_stderr(f_err):
                codigo = main()
        self.assertEqual(codigo, 1)

    def test_cli_resumo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            arq_in = Path(tmpdir) / "in.json"
            with patch("sys.argv", ["plano-corte-barras", "exemplo", "-o", str(arq_in)]):
                main()

            f = io.StringIO()
            with patch("sys.argv", ["plano-corte-barras", "resumo", "-i", str(arq_in)]):
                with redirect_stdout(f):
                    codigo = main()
            self.assertEqual(codigo, 0)
            self.assertIn("Roteiro de Corte de Oficina", f.getvalue())

    def test_cli_processar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            arq_in = Path(tmpdir) / "in.json"
            with patch("sys.argv", ["plano-corte-barras", "exemplo", "-o", str(arq_in)]):
                main()

            dir_saida = Path(tmpdir) / "saida"
            zip_saida = Path(tmpdir) / "corte.zip"

            with patch("sys.argv", [
                "plano-corte-barras", "processar",
                "-i", str(arq_in),
                "-d", str(dir_saida),
                "-z", str(zip_saida),
            ]):
                with redirect_stdout(io.StringIO()):
                    codigo = main()

            self.assertEqual(codigo, 0)
            self.assertTrue(zip_saida.exists())
            self.assertTrue((dir_saida / "plano-corte.csv").exists())
            self.assertTrue((dir_saida / "resumo-barras.csv").exists())
            self.assertTrue((dir_saida / "lista-corte.md").exists())
            self.assertTrue((dir_saida / "diagrama-corte.svg").exists())


if __name__ == "__main__":
    unittest.main()
