"""Testes do codec JSON estrito e canônico para plano-corte-barras."""

import unittest

from plano_corte_barras.errors import (
    ERR_JSON_BOM_PROIBIDO,
    ERR_JSON_CHAVE_DUPLICADA,
    ERR_JSON_FLOAT_PROIBIDO,
    ERR_JSON_INVALIDO,
    ERR_JSON_PROFUNDIDADE_EXCEDIDA,
    ERR_JSON_TAMANHO_EXCEDIDO,
    ErroCodificacaoJSON,
)
from plano_corte_barras.jsoncodec import (
    codificar_json_canonico,
    decodificar_json_estrito,
)


class TestJsonCodec(unittest.TestCase):
    def test_decodificacao_valida_bytes(self):
        dados = b'{"projeto": "Corte Galpao", "espessura": 3, "itens": [10, 20]}'
        res = decodificar_json_estrito(dados)
        self.assertEqual(res["projeto"], "Corte Galpao")
        self.assertEqual(res["espessura"], 3)
        self.assertEqual(res["itens"], [10, 20])

    def test_decodificacao_valida_str(self):
        dados = '{"ativo": true, "kerf": 4}'
        res = decodificar_json_estrito(dados)
        self.assertTrue(res["ativo"])
        self.assertEqual(res["kerf"], 4)

    def test_rejeicao_float(self):
        dados = b'{"comprimento_mm": 1200.5}'
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            decodificar_json_estrito(dados)
        self.assertEqual(ctx.exception.codigo, ERR_JSON_FLOAT_PROIBIDO)

    def test_rejeicao_float_em_lista(self):
        dados = b'{"barras": [6000, 12000, 5999.9]}'
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            decodificar_json_estrito(dados)
        self.assertEqual(ctx.exception.codigo, ERR_JSON_FLOAT_PROIBIDO)

    def test_rejeicao_bom_bytes(self):
        dados = b'\xef\xbb\xbf{"teste": 1}'
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            decodificar_json_estrito(dados)
        self.assertEqual(ctx.exception.codigo, ERR_JSON_BOM_PROIBIDO)

    def test_rejeicao_bom_str(self):
        dados = '\ufeff{"teste": 1}'
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            decodificar_json_estrito(dados)
        self.assertEqual(ctx.exception.codigo, ERR_JSON_BOM_PROIBIDO)

    def test_rejeicao_chave_duplicada(self):
        dados = b'{"comprimento": 6000, "comprimento": 12000}'
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            decodificar_json_estrito(dados)
        self.assertEqual(ctx.exception.codigo, ERR_JSON_CHAVE_DUPLICADA)

    def test_rejeicao_profundidade_excessiva(self):
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            json_profundo = '{"n":' * 35 + '1' + '}' * 35
            decodificar_json_estrito(json_profundo.encode("utf-8"))
        self.assertEqual(ctx.exception.codigo, ERR_JSON_PROFUNDIDADE_EXCEDIDA)

    def test_rejeicao_tamanho_excedido(self):
        dados = b'{"a": 1}'
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            decodificar_json_estrito(dados, limite_bytes=5)
        self.assertEqual(ctx.exception.codigo, ERR_JSON_TAMANHO_EXCEDIDO)

    def test_rejeicao_sintaxe_invalida(self):
        dados = b'{"invalido": '
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            decodificar_json_estrito(dados)
        self.assertEqual(ctx.exception.codigo, ERR_JSON_INVALIDO)

    def test_rejeicao_tipo_invalido(self):
        with self.assertRaises(ErroCodificacaoJSON) as ctx:
            decodificar_json_estrito(123)  # type: ignore
        self.assertEqual(ctx.exception.codigo, ERR_JSON_INVALIDO)

    def test_codificacao_canonica_estavel(self):
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        self.assertEqual(codificar_json_canonico(d1), codificar_json_canonico(d2))


if __name__ == "__main__":
    unittest.main()
