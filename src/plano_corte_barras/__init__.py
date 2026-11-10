"""plano-corte-barras: Otimização determinística de corte unidimensional (1D) de barras, perfis e tubos."""

__version__ = "1.0.0"

from .core import (
    BarraCortada,
    BarraEstoque,
    PecaCortada,
    PecaDemanda,
    ResultadoOtimizacao,
    ResumoGlobal,
    formatar_fracao_percentual,
    formatar_moeda_centavos,
    otimizar_plano_corte,
)
from .errors import (
    ErroCodificacaoJSON,
    ErroExecucao,
    ErroInviavel,
    ErroValidacaoEntrada,
    PlanoCorteError,
)
from .jsoncodec import (
    codificar_json_canonico,
    decodificar_json_estrito,
)
from .reports import (
    gerar_csv_plano_corte,
    gerar_csv_resumo_barras,
    gerar_dicionario_resultado,
    gerar_lista_corte_markdown,
    gerar_painel_svg,
    publicar_pacote_zip,
    sanitizar_campo_csv,
)

__all__ = [
    "__version__",
    "PlanoCorteError",
    "ErroCodificacaoJSON",
    "ErroValidacaoEntrada",
    "ErroInviavel",
    "ErroExecucao",
    "BarraEstoque",
    "PecaDemanda",
    "PecaCortada",
    "BarraCortada",
    "ResumoGlobal",
    "ResultadoOtimizacao",
    "otimizar_plano_corte",
    "formatar_fracao_percentual",
    "formatar_moeda_centavos",
    "decodificar_json_estrito",
    "codificar_json_canonico",
    "sanitizar_campo_csv",
    "gerar_csv_plano_corte",
    "gerar_csv_resumo_barras",
    "gerar_lista_corte_markdown",
    "gerar_dicionario_resultado",
    "gerar_painel_svg",
    "publicar_pacote_zip",
]
