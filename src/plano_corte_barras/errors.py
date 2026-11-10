"""Módulo de exceções e códigos de erro para o plano de corte de barras."""

from typing import Optional


class PlanoCorteError(Exception):
    """Exceção base para todas as falhas de domínio e validação."""

    def __init__(self, codigo: str, mensagem: str, detalhe: Optional[dict] = None) -> None:
        super().__init__(f"[{codigo}] {mensagem}")
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhe = detalhe or {}


class ErroCodificacaoJSON(PlanoCorteError):
    """Falhas na decodificação ou validação estrita do JSON."""
    pass


class ErroValidacaoEntrada(PlanoCorteError):
    """Inconsistência nos dados de entrada (barras, peças, comprimentos)."""
    pass


class ErroInviavel(PlanoCorteError):
    """Quando uma peça excede o tamanho máximo de barra disponível no estoque."""
    pass


class ErroExecucao(PlanoCorteError):
    """Falhas durante o processamento, geração de relatórios ou arquivos."""
    pass


# Constantes de códigos de erro
ERR_JSON_INVALIDO = "JSON_INVALIDO"
ERR_JSON_FLOAT_PROIBIDO = "JSON_FLOAT_PROIBIDO"
ERR_JSON_CHAVE_DUPLICADA = "JSON_CHAVE_DUPLICADA"
ERR_JSON_PROFUNDIDADE_EXCEDIDA = "JSON_PROFUNDIDADE_EXCEDIDA"
ERR_JSON_BOM_PROIBIDO = "JSON_BOM_PROIBIDO"
ERR_JSON_TAMANHO_EXCEDIDO = "JSON_TAMANHO_EXCEDIDO"

ERR_ESTOQUE_VAZIO = "ESTOQUE_VAZIO"
ERR_DEMANDA_VAZIA = "DEMANDA_VAZIA"
ERR_PECA_MAIOR_QUE_BARRA = "PECA_MAIOR_QUE_BARRA"
ERR_ESTOQUE_INSUFICIENTE = "ESTOQUE_INSUFICIENTE"
ERR_COMPRIMENTO_INVALIDO = "COMPRIMENTO_INVALIDO"
ERR_QUANTIDADE_INVALIDA = "QUANTIDADE_INVALIDA"
ERR_PARAMETRO_INVALIDO = "PARAMETRO_INVALIDO"
ERR_PERFIL_INCOMPATIVEL = "PERFIL_INCOMPATIVEL"
ERR_VALOR_INVALIDO = "VALOR_INVALIDO"
ERR_ARQUIVO_EXISTENTE = "ARQUIVO_EXISTENTE"
