"""Codec JSON estrito e canônico sem ponto flutuante, BOM ou chaves repetidas."""

import json
from typing import Any, List, Tuple

from .errors import (
    ERR_JSON_BOM_PROIBIDO,
    ERR_JSON_CHAVE_DUPLICADA,
    ERR_JSON_FLOAT_PROIBIDO,
    ERR_JSON_INVALIDO,
    ERR_JSON_PROFUNDIDADE_EXCEDIDA,
    ERR_JSON_TAMANHO_EXCEDIDO,
    ErroCodificacaoJSON,
)

LIMITE_TAMANHO_PADRAO_BYTES = 10 * 1024 * 1024  # 10 MiB
LIMITE_PROFUNDIDADE_PADRAO = 32


def _rejeitar_float(valor: str) -> None:
    raise ErroCodificacaoJSON(
        ERR_JSON_FLOAT_PROIBIDO,
        f"Ponto flutuante proibido na entrada: '{valor}'. Utilize inteiros (milímetros, unidades, centavos).",
    )


def _pares_sem_duplicatas(pares: List[Tuple[str, Any]]) -> dict:
    dicionario = {}
    for chave, valor in pares:
        if chave in dicionario:
            raise ErroCodificacaoJSON(
                ERR_JSON_CHAVE_DUPLICADA,
                f"Chave duplicada proibida no objeto JSON: '{chave}'.",
            )
        dicionario[chave] = valor
    return dicionario


def _verificar_profundidade(obj: Any, profundidade_atual: int = 1, limite: int = LIMITE_PROFUNDIDADE_PADRAO) -> None:
    if profundidade_atual > limite:
        raise ErroCodificacaoJSON(
            ERR_JSON_PROFUNDIDADE_EXCEDIDA,
            f"Profundidade da estrutura JSON ({profundidade_atual}) excedeu o limite máximo permitido ({limite}).",
        )
    if isinstance(obj, dict):
        for v in obj.values():
            _verificar_profundidade(v, profundidade_atual + 1, limite)
    elif isinstance(obj, list):
        for item in obj:
            _verificar_profundidade(item, profundidade_atual + 1, limite)


def decodificar_json_estrito(dados_bytes_ou_str: Any, limite_bytes: int = LIMITE_TAMANHO_PADRAO_BYTES) -> Any:
    """Decodifica JSON exigindo UTF-8 sem BOM, sem números float e sem chaves repetidas."""
    if isinstance(dados_bytes_ou_str, bytes):
        if dados_bytes_ou_str.startswith(b"\xef\xbb\xbf"):
            raise ErroCodificacaoJSON(
                ERR_JSON_BOM_PROIBIDO,
                "Assinatura Byte Order Mark (BOM) UTF-8 proibida no arquivo JSON.",
            )
        if len(dados_bytes_ou_str) > limite_bytes:
            raise ErroCodificacaoJSON(
                ERR_JSON_TAMANHO_EXCEDIDO,
                f"Tamanho do arquivo ({len(dados_bytes_ou_str)} bytes) excede o limite máximo ({limite_bytes} bytes).",
            )
        try:
            texto = dados_bytes_ou_str.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ErroCodificacaoJSON(
                ERR_JSON_INVALIDO,
                f"Codificação inválida: esperado UTF-8 estrito. Detalhe: {err}",
            )
    elif isinstance(dados_bytes_ou_str, str):
        if dados_bytes_ou_str.startswith("\ufeff"):
            raise ErroCodificacaoJSON(
                ERR_JSON_BOM_PROIBIDO,
                "Assinatura Byte Order Mark (BOM) UTF-8 proibida no texto JSON.",
            )
        texto = dados_bytes_ou_str
    else:
        raise ErroCodificacaoJSON(
            ERR_JSON_INVALIDO,
            f"Entrada inválida para decodificação: esperado bytes ou str, recebido {type(dados_bytes_ou_str).__name__}.",
        )

    try:
        estrutura = json.loads(
            texto,
            parse_float=_rejeitar_float,
            object_pairs_hook=_pares_sem_duplicatas,
        )
    except json.JSONDecodeError as err:
        raise ErroCodificacaoJSON(
            ERR_JSON_INVALIDO,
            f"Sintaxe JSON inválida na linha {err.lineno}, coluna {err.colno}: {err.msg}",
        )

    _verificar_profundidade(estrutura, 1, LIMITE_PROFUNDIDADE_PADRAO)
    return estrutura


def codificar_json_canonico(obj: Any) -> str:
    """Codifica objeto Python em JSON formatado de maneira estável e determinística."""
    return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
