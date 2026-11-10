"""Interface de linha de comando (CLI) para plano-corte-barras."""

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Dict

# Assegura suporte a UTF-8 no console mesmo em Windows com charmap/cp1252
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from . import __version__
from .core import formatar_moeda_centavos, otimizar_plano_corte
from .errors import PlanoCorteError
from .jsoncodec import codificar_json_canonico, decodificar_json_estrito
from .reports import (
    gerar_csv_plano_corte,
    gerar_csv_resumo_barras,
    gerar_dicionario_resultado,
    gerar_lista_corte_markdown,
    gerar_painel_svg,
    publicar_pacote_zip,
)

EXEMPLO_CANONICO = {
    "projeto": {
        "nome": "Estrutura Metálica Galpão Industrial Modulado",
    },
    "parametros": {
        "espessura_corte_mm": 3,
        "comprimento_minimo_aproveitavel_mm": 500,
        "margem_seguranca_ponta_mm": 10,
    },
    "estoque_barras": [
        {
            "id": "BARRA-6M-TUBO50",
            "perfil": "TUBO_50X50_2MM",
            "comprimento_mm": 6000,
            "quantidade": 15,
            "custo_unitario_centavos": 14500,
        },
        {
            "id": "BARRA-12M-CA50",
            "perfil": "VERGALHAO_CA50_10MM",
            "comprimento_mm": 12000,
            "quantidade": 20,
            "custo_unitario_centavos": 4200,
        },
    ],
    "pecas_demandadas": [
        {"id": "MONTANTE-A", "perfil": "TUBO_50X50_2MM", "comprimento_mm": 2400, "quantidade": 6, "descricao": "Montante Vertical Principal"},
        {"id": "TRAVESSA-B", "perfil": "TUBO_50X50_2MM", "comprimento_mm": 1800, "quantidade": 8, "descricao": "Travessa Horizontal de Reforço"},
        {"id": "DIAGONAL-C", "perfil": "TUBO_50X50_2MM", "comprimento_mm": 1150, "quantidade": 12, "descricao": "Tirante Diagonal Contraventamento"},
        {"id": "ESTRIBO-P1", "perfil": "VERGALHAO_CA50_10MM", "comprimento_mm": 3400, "quantidade": 10, "descricao": "Armadura Longitudinal Pilar P1"},
        {"id": "ESTRIBO-P2", "perfil": "VERGALHAO_CA50_10MM", "comprimento_mm": 2850, "quantidade": 14, "descricao": "Armadura Longitudinal Pilar P2"},
        {"id": "VIGA-V1", "perfil": "VERGALHAO_CA50_10MM", "comprimento_mm": 4200, "quantidade": 8, "descricao": "Reforço Positivo Viga V1"},
    ],
}


def cmd_versao(_args: argparse.Namespace) -> int:
    print(f"plano-corte-barras {__version__}")
    return 0


def cmd_exemplo(args: argparse.Namespace) -> int:
    saida_str = codificar_json_canonico(EXEMPLO_CANONICO)
    if args.saida:
        p = Path(args.saida)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(saida_str, encoding="utf-8")
        print(f"Exemplo canônico gravado em: {p}")
    else:
        sys.stdout.write(saida_str)
    return 0


def cmd_verificar(args: argparse.Namespace) -> int:
    caminho = Path(args.entrada)
    if not caminho.exists():
        print(f"Erro: arquivo de entrada não encontrado: {caminho}", file=sys.stderr)
        return 1

    dados = decodificar_json_estrito(caminho.read_bytes())
    resultado = otimizar_plano_corte(dados)
    r = resultado.resumo_global
    print("✓ Entrada válida e viável para corte.")
    print(f"  Projeto: {resultado.projeto_nome}")
    print(f"  Barras consumidas: {r.total_barras_utilizadas}")
    print(f"  Aproveitamento global: {r.aproveitamento_global_percentual}")
    print(f"  Custo total de material: {formatar_moeda_centavos(r.total_custo_centavos)}")
    return 0


def cmd_resumo(args: argparse.Namespace) -> int:
    caminho = Path(args.entrada)
    if not caminho.exists():
        print(f"Erro: arquivo de entrada não encontrado: {caminho}", file=sys.stderr)
        return 1

    dados = decodificar_json_estrito(caminho.read_bytes())
    resultado = otimizar_plano_corte(dados)
    md = gerar_lista_corte_markdown(resultado)
    sys.stdout.write(md)
    return 0


def cmd_processar(args: argparse.Namespace) -> int:
    caminho_entrada = Path(args.entrada)
    if not caminho_entrada.exists():
        print(f"Erro: arquivo de entrada não encontrado: {caminho_entrada}", file=sys.stderr)
        return 1

    dados_bytes = caminho_entrada.read_bytes()
    dados = decodificar_json_estrito(dados_bytes)
    resultado = otimizar_plano_corte(dados)

    csv_plano = gerar_csv_plano_corte(resultado)
    csv_resumo = gerar_csv_resumo_barras(resultado)
    md_lista = gerar_lista_corte_markdown(resultado)
    svg_painel = gerar_painel_svg(resultado)
    json_resultado = codificar_json_canonico(gerar_dicionario_resultado(resultado))

    arquivos_zip: Dict[str, bytes] = {
        "entrada.json": dados_bytes,
        "plano.json": json_resultado.encode("utf-8"),
        "plano-corte.csv": csv_plano.encode("utf-8"),
        "resumo-barras.csv": csv_resumo.encode("utf-8"),
        "lista-corte.md": md_lista.encode("utf-8"),
        "diagrama-corte.svg": svg_painel.encode("utf-8"),
    }

    linhas_sha = []
    for nome in sorted(arquivos_zip.keys()):
        h = hashlib.sha256(arquivos_zip[nome]).hexdigest()
        linhas_sha.append(f"{h}  {nome}")
    arquivos_zip["SHA256SUMS"] = ("\n".join(linhas_sha) + "\n").encode("utf-8")

    if args.saida_dir:
        dir_saida = Path(args.saida_dir)
        dir_saida.mkdir(parents=True, exist_ok=True)
        for nome, conteudo in arquivos_zip.items():
            (dir_saida / nome).write_bytes(conteudo)
        print(f"Artefatos analíticos gravados em: {dir_saida}")

    if args.zip:
        caminho_zip = Path(args.zip)
        caminho_zip.parent.mkdir(parents=True, exist_ok=True)
        publicar_pacote_zip(caminho_zip, arquivos_zip)
        print(f"Pacote ZIP determinístico publicado em: {caminho_zip}")

    r = resultado.resumo_global
    print(f"✓ Plano de corte gerado: {r.total_barras_utilizadas} barras, aproveitamento de {r.aproveitamento_global_percentual}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plano-corte-barras",
        description="Otimização determinística de corte 1D de barras, tubos e perfis metálicos.",
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    sub_ver = subparsers.add_parser("versao", help="Exibe a versão do pacote")
    sub_ver.set_defaults(func=cmd_versao)

    sub_ex = subparsers.add_parser("exemplo", help="Emite o modelo canônico de entrada JSON")
    sub_ex.add_argument("--saida", "-o", help="Caminho do arquivo de saída (opcional)")
    sub_ex.set_defaults(func=cmd_exemplo)

    sub_chk = subparsers.add_parser("verificar", help="Valida viabilidade das peças e do estoque")
    sub_chk.add_argument("--entrada", "-i", required=True, help="Arquivo JSON de entrada")
    sub_chk.set_defaults(func=cmd_verificar)

    sub_res = subparsers.add_parser("resumo", help="Exibe resumo do plano de corte em Markdown")
    sub_res.add_argument("--entrada", "-i", required=True, help="Arquivo JSON de entrada")
    sub_res.set_defaults(func=cmd_resumo)

    sub_proc = subparsers.add_parser("processar", help="Otimiza o corte e exporta CSV, Markdown, SVG e ZIP")
    sub_proc.add_argument("--entrada", "-i", required=True, help="Arquivo JSON de entrada")
    sub_proc.add_argument("--saida-dir", "-d", help="Diretório para salvar os artefatos gerados")
    sub_proc.add_argument("--zip", "-z", help="Caminho para criar o arquivo ZIP consolidado")
    sub_proc.set_defaults(func=cmd_processar)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except PlanoCorteError as err:
        print(f"Erro [{err.codigo}]: {err.mensagem}", file=sys.stderr)
        return 2
    except Exception as err:
        print(f"Erro inesperado: {err}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
