"""Módulo de geração de relatórios, CSV, lista de oficina Markdown, painel SVG e ZIP."""

import csv
import io
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from .core import ResultadoOtimizacao, formatar_fracao_percentual, formatar_moeda_centavos
from .errors import ERR_ARQUIVO_EXISTENTE, ErroExecucao


def sanitizar_campo_csv(valor: Any) -> str:
    """Prevenção contra injeção de fórmulas CSV (=, +, -, @, \\t, \\r)."""
    texto = str(valor)
    if texto and texto[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{texto}"
    return texto


def gerar_csv_plano_corte(resultado: ResultadoOtimizacao) -> str:
    """Gera CSV detalhado corte a corte para a fábrica/oficina."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    cabecalho = [
        "indice_barra",
        "barra_estoque_id",
        "perfil",
        "comprimento_total_mm",
        "sequencia_corte",
        "peca_id",
        "descricao",
        "posicao_inicio_mm",
        "posicao_fim_mm",
        "comprimento_peca_mm",
        "perda_kerf_mm",
    ]
    writer.writerow([sanitizar_campo_csv(c) for c in cabecalho])

    for b in resultado.barras_cortadas:
        for seq, p in enumerate(b.pecas, start=1):
            writer.writerow([
                str(b.indice_barra),
                sanitizar_campo_csv(b.barra_estoque_id),
                sanitizar_campo_csv(b.perfil),
                str(b.comprimento_total_mm),
                str(seq),
                sanitizar_campo_csv(p.peca_id),
                sanitizar_campo_csv(p.descricao),
                str(p.posicao_inicio_mm),
                str(p.posicao_fim_mm),
                str(p.comprimento_mm),
                str(p.perda_corte_mm),
            ])

    return buffer.getvalue()


def gerar_csv_resumo_barras(resultado: ResultadoOtimizacao) -> str:
    """Gera CSV com os totais de cada barra bruta consumida."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    cabecalho = [
        "indice_barra",
        "barra_estoque_id",
        "perfil",
        "comprimento_total_mm",
        "qtd_pecas",
        "comprimento_util_mm",
        "perda_cortes_mm",
        "refugo_ponta_mm",
        "sobra_final_mm",
        "tipo_sobra",
        "aproveitamento_percentual",
        "custo_centavos",
        "custo_formatado",
    ]
    writer.writerow([sanitizar_campo_csv(c) for c in cabecalho])

    for b in resultado.barras_cortadas:
        writer.writerow([
            str(b.indice_barra),
            sanitizar_campo_csv(b.barra_estoque_id),
            sanitizar_campo_csv(b.perfil),
            str(b.comprimento_total_mm),
            str(len(b.pecas)),
            str(b.comprimento_util_pecas_mm),
            str(b.perda_cortes_total_mm),
            str(b.refugo_ponta_mm),
            str(b.sobra_final_mm),
            sanitizar_campo_csv(b.tipo_sobra),
            sanitizar_campo_csv(formatar_fracao_percentual(b.taxa_aproveitamento, casas=2)),
            str(b.custo_unitario_centavos),
            sanitizar_campo_csv(formatar_moeda_centavos(b.custo_unitario_centavos)),
        ])

    return buffer.getvalue()


def gerar_lista_corte_markdown(resultado: ResultadoOtimizacao) -> str:
    """Gera roteiro operacional de corte para a oficina em Markdown."""
    r = resultado.resumo_global
    linhas = [
        f"# Roteiro de Corte de Oficina — {resultado.projeto_nome}",
        "",
        f"- **Espessura do Disco (Kerf):** `{resultado.espessura_corte_mm} mm`",
        f"- **Comprimento Mínimo de Sobra Aproveitável:** `{resultado.comprimento_minimo_aproveitavel_mm} mm`",
        f"- **Margem de Segurança de Ponta:** `{resultado.margem_seguranca_ponta_mm} mm`",
        f"- **Aproveitamento Global:** **{r.aproveitamento_global_percentual}** (Perda: {r.perda_global_percentual})",
        f"- **Barras Utilizadas:** `{r.total_barras_utilizadas}`",
        f"- **Custo Total do Material:** **{formatar_moeda_centavos(r.total_custo_centavos)}**",
        "",
        "## 1. Balanço Global de Material",
        "",
        "| Rubrica | Comprimento (mm) | Proporção |",
        "| :--- | :--- | :--- |",
        f"| Comprimento Útil (Peças Cortadas) | `{r.total_comprimento_util_mm}` mm | {r.aproveitamento_global_percentual} |",
        f"| Sobras Aproveitáveis (Retalhos em Estoque) | `{r.total_sobra_aproveitavel_mm}` mm | {formatar_fracao_percentual(r.total_sobra_aproveitavel_mm / (r.total_comprimento_bruto_mm or 1) * 100 if False else r.aproveitamento_global_fracao, casas=2)} |",
        f"| Perdas em Cortes (Cavacos de Serra) | `{r.total_perda_cortes_mm}` mm | - |",
        f"| Sucata Descartável | `{r.total_sucata_descarte_mm}` mm | - |",
        f"| **Comprimento Bruto Total** | `{r.total_comprimento_bruto_mm}` mm | **100%** |",
        "",
        "## 2. Instruções de Corte Barra a Barra",
        "",
    ]

    for b in resultado.barras_cortadas:
        linhas.append(f"### Barra #{b.indice_barra} — Perfil `{b.perfil}` ({b.comprimento_total_mm} mm) — Barra `{b.barra_estoque_id}`")
        linhas.append(f"- **Aproveitamento:** `{formatar_fracao_percentual(b.taxa_aproveitamento)}` | **Sobra Final:** `{b.sobra_final_mm} mm` ({b.tipo_sobra})")
        linhas.append("")
        linhas.append("| Seq | Peça | Descrição | Comprimento | Início | Fim | Kerf |")
        linhas.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for seq, p in enumerate(b.pecas, start=1):
            linhas.append(
                f"| {seq} | `{p.peca_id}` | {p.descricao} | `{p.comprimento_mm} mm` | `{p.posicao_inicio_mm} mm` | `{p.posicao_fim_mm} mm` | `{p.perda_corte_mm} mm` |"
            )
        linhas.append("")

    linhas.extend([
        "---",
        "*Gerado por LOFRANO TECNOLOGIA — plano-corte-barras*",
    ])

    return "\n".join(linhas) + "\n"


def gerar_dicionario_resultado(resultado: ResultadoOtimizacao) -> dict:
    """Estrutura os dados para exportação JSON canônica."""
    r = resultado.resumo_global
    return {
        "projeto": {
            "nome": resultado.projeto_nome,
            "espessura_corte_mm": resultado.espessura_corte_mm,
            "comprimento_minimo_aproveitavel_mm": resultado.comprimento_minimo_aproveitavel_mm,
            "margem_seguranca_ponta_mm": resultado.margem_seguranca_ponta_mm,
        },
        "resumo_global": {
            "total_barras_utilizadas": r.total_barras_utilizadas,
            "total_comprimento_bruto_mm": r.total_comprimento_bruto_mm,
            "total_comprimento_util_mm": r.total_comprimento_util_mm,
            "total_perda_cortes_mm": r.total_perda_cortes_mm,
            "total_refugo_ponta_mm": r.total_refugo_ponta_mm,
            "total_sobra_aproveitavel_mm": r.total_sobra_aproveitavel_mm,
            "total_sucata_descarte_mm": r.total_sucata_descarte_mm,
            "total_custo_centavos": r.total_custo_centavos,
            "aproveitamento_global_percentual": r.aproveitamento_global_percentual,
            "perda_global_percentual": r.perda_global_percentual,
        },
        "barras_cortadas": [
            {
                "indice_barra": b.indice_barra,
                "barra_estoque_id": b.barra_estoque_id,
                "perfil": b.perfil,
                "comprimento_total_mm": b.comprimento_total_mm,
                "custo_unitario_centavos": b.custo_unitario_centavos,
                "refugo_ponta_mm": b.refugo_ponta_mm,
                "sobra_final_mm": b.sobra_final_mm,
                "tipo_sobra": b.tipo_sobra,
                "taxa_aproveitamento_percentual": formatar_fracao_percentual(b.taxa_aproveitamento, casas=2),
                "pecas": [
                    {
                        "peca_id": p.peca_id,
                        "descricao": p.descricao,
                        "comprimento_mm": p.comprimento_mm,
                        "posicao_inicio_mm": p.posicao_inicio_mm,
                        "posicao_fim_mm": p.posicao_fim_mm,
                        "perda_corte_mm": p.perda_corte_mm,
                    }
                    for p in b.pecas
                ],
            }
            for b in resultado.barras_cortadas
        ],
    }


def gerar_painel_svg(resultado: ResultadoOtimizacao) -> str:
    """Gera painel visual de alta fidelidade em SVG (1440x900) com barras e plano de corte."""
    r = resultado.resumo_global
    barras_exibir = resultado.barras_cortadas[:7]
    comp_max = max((b.comprimento_total_mm for b in resultado.barras_cortadas), default=6000)

    # Paleta de cores para as peças
    cores_pecas = [
        "#38BDF8", "#34D399", "#FBBF24", "#F472B6",
        "#A78BFA", "#FB923C", "#4ADE80", "#E879F9",
    ]

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="900" viewBox="0 0 1440 900">',
        '  <defs>',
        '    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">',
        '      <stop offset="0%" stop-color="#0C101B" />',
        '      <stop offset="100%" stop-color="#151B29" />',
        '    </linearGradient>',
        '    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="0%" y2="100%">',
        '      <stop offset="0%" stop-color="#1E293B" stop-opacity="0.8" />',
        '      <stop offset="100%" stop-color="#0F172A" stop-opacity="0.9" />',
        '    </linearGradient>',
        '  </defs>',
        '  <rect width="1440" height="900" fill="url(#bg)" />',
        '',
        '  <!-- Cabeçalho -->',
        '  <g transform="translate(60, 45)">',
        f'    <text x="0" y="32" font-family="system-ui, -apple-system, sans-serif" font-size="28" font-weight="700" fill="#F8FAFC">{resultado.projeto_nome}</text>',
        f'    <text x="0" y="60" font-family="system-ui, -apple-system, sans-serif" font-size="15" fill="#94A3B8">Otimização Determinística de Corte 1D · Kerf: {resultado.espessura_corte_mm} mm · LOFRANO TECNOLOGIA</text>',
        '    <rect x="1110" y="10" width="210" height="42" rx="8" fill="#065F46" />',
        f'    <text x="1215" y="36" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="600" fill="#34D399" text-anchor="middle">✓ APROVEITAMENTO: {r.aproveitamento_global_percentual}</text>',
        '  </g>',
        '',
        '  <!-- 4 Cards de Métricas -->',
        '  <g transform="translate(60, 135)">',
        '    <!-- Card 1 -->',
        '    <rect x="0" y="0" width="310" height="105" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1" />',
        '    <text x="24" y="34" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#94A3B8">BARRAS CONSUMIDAS</text>',
        f'    <text x="24" y="70" font-family="system-ui, sans-serif" font-size="26" font-weight="700" fill="#38BDF8">{r.total_barras_utilizadas} barras</text>',
        f'    <text x="24" y="92" font-family="system-ui, sans-serif" font-size="12" fill="#64748B">{r.total_comprimento_bruto_mm:,} mm brutos</text>',
        '',
        '    <!-- Card 2 -->',
        '    <rect x="336" y="0" width="310" height="105" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1" />',
        '    <text x="360" y="34" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#94A3B8">COMPRIMENTO ÚTIL</text>',
        f'    <text x="360" y="70" font-family="system-ui, sans-serif" font-size="26" font-weight="700" fill="#34D399">{r.total_comprimento_util_mm:,} mm</text>',
        f'    <text x="360" y="92" font-family="system-ui, sans-serif" font-size="12" fill="#64748B">{sum(len(b.pecas) for b in resultado.barras_cortadas)} peças cortadas</text>',
        '',
        '    <!-- Card 3 -->',
        '    <rect x="672" y="0" width="310" height="105" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1" />',
        '    <text x="696" y="34" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#94A3B8">SOBRAS E RETALHOS</text>',
        f'    <text x="696" y="70" font-family="system-ui, sans-serif" font-size="26" font-weight="700" fill="#FBBF24">{r.total_sobra_aproveitavel_mm:,} mm</text>',
        f'    <text x="696" y="92" font-family="system-ui, sans-serif" font-size="12" fill="#64748B">Sucata: {r.total_sucata_descarte_mm:,} mm</text>',
        '',
        '    <!-- Card 4 -->',
        '    <rect x="1008" y="0" width="312" height="105" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1" />',
        '    <text x="1032" y="34" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#94A3B8">CUSTO TOTAL DO MATERIAL</text>',
        f'    <text x="1032" y="70" font-family="system-ui, sans-serif" font-size="26" font-weight="700" fill="#F8FAFC">{formatar_moeda_centavos(r.total_custo_centavos)}</text>',
        f'    <text x="1032" y="92" font-family="system-ui, sans-serif" font-size="12" fill="#64748B">Perda de kerf: {r.total_perda_cortes_mm:,} mm</text>',
        '  </g>',
        '',
        '  <!-- Diagrama de Corte Barra a Barra -->',
        '  <g transform="translate(60, 275)">',
        '    <rect x="0" y="0" width="1320" height="570" rx="14" fill="url(#cardGrad)" stroke="#334155" stroke-width="1" />',
        '    <text x="32" y="40" font-family="system-ui, sans-serif" font-size="18" font-weight="700" fill="#F8FAFC">Diagrama de Distribuição de Corte nas Barras</text>',
        '    <text x="32" y="64" font-family="system-ui, sans-serif" font-size="13" fill="#94A3B8">Representação proporcional milimétrica de peças cortadas (coloridas) e sobras (cinza)</text>',
    ]

    y_offset = 100
    largura_max_grafico = 1000

    for b in barras_exibir:
        largura_barra_px = int((b.comprimento_total_mm / comp_max) * largura_max_grafico)
        svg.extend([
            f'    <!-- Barra #{b.indice_barra} -->',
            f'    <text x="32" y="{y_offset + 22}" font-family="system-ui, sans-serif" font-size="13" font-weight="600" fill="#CBD5E1">Barra #{b.indice_barra} ({b.comprimento_total_mm} mm)</text>',
            f'    <rect x="220" y="{y_offset}" width="{largura_barra_px}" height="32" rx="4" fill="#334155" />',
        ])

        # Renderiza cada peça dentro da barra
        for idx_p, p in enumerate(b.pecas):
            x_ini = 220 + int((p.posicao_inicio_mm / comp_max) * largura_max_grafico)
            w_peca = max(2, int((p.comprimento_mm / comp_max) * largura_max_grafico))
            cor = cores_pecas[idx_p % len(cores_pecas)]
            svg.append(f'    <rect x="{x_ini}" y="{y_offset}" width="{w_peca}" height="32" fill="{cor}" stroke="#0F172A" stroke-width="1" />')

        # Taxa de aproveitamento da barra
        svg.extend([
            f'    <text x="{235 + largura_barra_px}" y="{y_offset + 22}" font-family="system-ui, sans-serif" font-size="13" font-weight="700" fill="#38BDF8">{formatar_fracao_percentual(b.taxa_aproveitamento)}</text>',
        ])
        y_offset += 62

    # Legenda inferior
    svg.extend([
        '    <g transform="translate(32, 530)">',
        '      <rect x="0" y="0" width="16" height="16" rx="3" fill="#38BDF8" />',
        '      <text x="24" y="13" font-family="system-ui, sans-serif" font-size="12" fill="#94A3B8">Peças Cortadas (Úteis)</text>',
        '      <rect x="200" y="0" width="16" height="16" rx="3" fill="#334155" />',
        '      <text x="224" y="13" font-family="system-ui, sans-serif" font-size="12" fill="#94A3B8">Sobra / Retalho</text>',
        '      <rect x="360" y="0" width="16" height="16" rx="3" fill="#065F46" />',
        '      <text x="384" y="13" font-family="system-ui, sans-serif" font-size="12" fill="#94A3B8">Conservação 100% Milimétrica</text>',
        '    </g>',
        '  </g>',
        '</svg>',
    ])
    return "\n".join(svg) + "\n"


def publicar_pacote_zip(
    caminho_zip: Path,
    arquivos: Dict[str, bytes],
) -> None:
    """Cria arquivo ZIP determinístico com garantia de não sobrescrita atômica."""
    caminho_zip = Path(caminho_zip)
    if caminho_zip.exists():
        raise ErroExecucao(ERR_ARQUIVO_EXISTENTE, f"Arquivo de destino já existe: {caminho_zip}")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(str(caminho_zip), flags, 0o644)
    except FileExistsError:
        raise ErroExecucao(ERR_ARQUIVO_EXISTENTE, f"Arquivo de destino já existe: {caminho_zip}")

    try:
        with os.fdopen(fd, "wb") as f_out:
            with zipfile.ZipFile(f_out, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                data_fixa = (2026, 11, 10, 0, 0, 0)
                for nome in sorted(arquivos.keys()):
                    conteudo = arquivos[nome]
                    zinfo = zipfile.ZipInfo(filename=nome, date_time=data_fixa)
                    zinfo.compress_type = zipfile.ZIP_DEFLATED
                    zinfo.external_attr = 0o644 << 16
                    zf.writestr(zinfo, conteudo)
    except Exception as err:
        if caminho_zip.exists():
            try:
                caminho_zip.unlink()
            except OSError:
                pass
        raise ErroExecucao(
            "FALHA_ZIP",
            f"Erro ao empacotar arquivo ZIP '{caminho_zip}': {err}",
        )
