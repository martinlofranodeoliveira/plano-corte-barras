#!/usr/bin/env python3
"""Auditor independente para plano-corte-barras sem importar o pacote de produção."""

import argparse
import csv
import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from fractions import Fraction
from pathlib import Path

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


def verificar_pacote_zip(caminho_zip: Path) -> bool:
    print(f"=== Auditoria Independente: {caminho_zip.name} ===")

    if not caminho_zip.exists():
        print(f"[ERRO] Arquivo ZIP não encontrado: {caminho_zip}", file=sys.stderr)
        return False

    with zipfile.ZipFile(caminho_zip, "r") as zf:
        nomes = set(zf.namelist())
        arquivos_obrigatorios = {
            "entrada.json",
            "plano.json",
            "plano-corte.csv",
            "resumo-barras.csv",
            "lista-corte.md",
            "diagrama-corte.svg",
            "SHA256SUMS",
        }
        faltantes = arquivos_obrigatorios - nomes
        if faltantes:
            print(f"[ERRO] Arquivos obrigatórios ausentes no ZIP: {faltantes}", file=sys.stderr)
            return False

        # 1. Conferência criptográfica SHA-256
        raw_sha = zf.read("SHA256SUMS").decode("utf-8")
        for linha in raw_sha.strip().splitlines():
            partes = linha.strip().split(maxsplit=1)
            if len(partes) != 2:
                continue
            hash_esperado, nome_arq = partes
            if nome_arq == "SHA256SUMS":
                continue
            conteudo = zf.read(nome_arq)
            hash_real = hashlib.sha256(conteudo).hexdigest()
            if hash_esperado != hash_real:
                print(f"[ERRO] Hash SHA-256 divergente para '{nome_arq}': esperado {hash_esperado}, obtido {hash_real}", file=sys.stderr)
                return False
        print("  ✓ Integridade criptográfica SHA-256 verificada com sucesso em todos os artefatos.")

        # 2. Carregamento da entrada original
        entrada = json.loads(zf.read("entrada.json").decode("utf-8"))
        pecas_demandadas = entrada.get("pecas_demandadas", [])
        demanda_esperada = {}
        for p in pecas_demandadas:
            chave = (p["id"], p["perfil"], p["comprimento_mm"])
            demanda_esperada[chave] = demanda_esperada.get(chave, 0) + p["quantidade"]

        # 3. Carga e auditoria relacional via SQLite em memória
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # Tabela resumo_barras
        cursor.execute("""
            CREATE TABLE resumo_barras (
                indice_barra INTEGER PRIMARY KEY,
                barra_estoque_id TEXT,
                perfil TEXT,
                comprimento_total_mm INTEGER,
                qtd_pecas INTEGER,
                comprimento_util_mm INTEGER,
                perda_cortes_mm INTEGER,
                refugo_ponta_mm INTEGER,
                sobra_final_mm INTEGER,
                tipo_sobra TEXT,
                aproveitamento_percentual TEXT,
                custo_centavos INTEGER,
                custo_formatado TEXT
            )
        """)

        csv_resumo = zf.read("resumo-barras.csv").decode("utf-8")
        leitor_r = csv.reader(io.StringIO(csv_resumo))
        next(leitor_r)
        for row in leitor_r:
            cursor.execute("""
                INSERT INTO resumo_barras VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row[0]), row[1], row[2], int(row[3]), int(row[4]),
                int(row[5]), int(row[6]), int(row[7]), int(row[8]), row[9],
                row[10], int(row[11]), row[12],
            ))

        # Tabela plano_corte
        cursor.execute("""
            CREATE TABLE plano_corte (
                indice_barra INTEGER,
                barra_estoque_id TEXT,
                perfil TEXT,
                comprimento_total_mm INTEGER,
                sequencia_corte INTEGER,
                peca_id TEXT,
                descricao TEXT,
                posicao_inicio_mm INTEGER,
                posicao_fim_mm INTEGER,
                comprimento_peca_mm INTEGER,
                perda_kerf_mm INTEGER
            )
        """)

        csv_plano = zf.read("plano-corte.csv").decode("utf-8")
        leitor_p = csv.reader(io.StringIO(csv_plano))
        next(leitor_p)
        for row in leitor_p:
            cursor.execute("""
                INSERT INTO plano_corte VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row[0]), row[1], row[2], int(row[3]), int(row[4]),
                row[5], row[6], int(row[7]), int(row[8]), int(row[9]),
                int(row[10]),
            ))

        conn.commit()

        # 4. Verificação de Conservação Milimétrica Barra a Barra
        cursor.execute("SELECT indice_barra, comprimento_total_mm, refugo_ponta_mm, sobra_final_mm FROM resumo_barras")
        barras = cursor.fetchall()

        for b_idx, comp_total, refugo, sobra in barras:
            cursor.execute("""
                SELECT SUM(comprimento_peca_mm), SUM(perda_kerf_mm), COUNT(*)
                FROM plano_corte WHERE indice_barra = ?
            """, (b_idx,))
            soma_pecas, soma_kerf, qtd_pecas = cursor.fetchone()
            soma_pecas = soma_pecas or 0
            soma_kerf = soma_kerf or 0

            soma_fechamento = refugo + soma_pecas + soma_kerf + sobra
            if soma_fechamento != comp_total:
                print(f"[ERRO] Conservação violada na barra #{b_idx}: {soma_fechamento} mm != {comp_total} mm", file=sys.stderr)
                return False

            # Verifica não sobreposição e limites geométricos
            cursor.execute("""
                SELECT sequencia_corte, posicao_inicio_mm, posicao_fim_mm, comprimento_peca_mm, perda_kerf_mm
                FROM plano_corte WHERE indice_barra = ? ORDER BY sequencia_corte
            """, (b_idx,))
            pecas_barra = cursor.fetchall()

            pos_esperada = refugo
            for seq, p_ini, p_fim, p_comp, p_perda in pecas_barra:
                if p_ini != pos_esperada:
                    print(f"[ERRO] Salto posicional na barra #{b_idx}, seq {seq}: início {p_ini} != esperado {pos_esperada}", file=sys.stderr)
                    return False
                if p_fim != p_ini + p_comp:
                    print(f"[ERRO] Comprimento inconsistente na barra #{b_idx}, seq {seq}: fim {p_fim} != ini+comp {p_ini+p_comp}", file=sys.stderr)
                    return False
                pos_esperada = p_fim + p_perda

            if pos_esperada + sobra != comp_total:
                print(f"[ERRO] Sobra inconsistente na barra #{b_idx}: pos {pos_esperada} + sobra {sobra} != total {comp_total}", file=sys.stderr)
                return False

        print(f"  ✓ Conservação e alinhamento geométrico milimétrico confirmados em todas as {len(barras)} barras.")

        # 5. Verificação da Demanda Total Cortada
        cursor.execute("""
            SELECT peca_id, perfil, comprimento_peca_mm, COUNT(*)
            FROM plano_corte GROUP BY peca_id, perfil, comprimento_peca_mm
        """)
        cortes_realizados = cursor.fetchall()
        demanda_atendida = {}
        for pid, perf, comp, qtd in cortes_realizados:
            demanda_atendida[(pid, perf, comp)] = qtd

        if demanda_atendida != demanda_esperada:
            print(f"[ERRO] Divergência entre demanda esperada e peças cortadas:\nEsperado: {demanda_esperada}\nObtido: {demanda_atendida}", file=sys.stderr)
            return False

        total_pecas_cortadas = sum(demanda_atendida.values())
        print(f"  ✓ Todas as {total_pecas_cortadas} peças demandadas foram cortadas com dimensões exatas.")

        # 6. Verificação do Aproveitamento Global Racional
        cursor.execute("SELECT SUM(comprimento_util_mm), SUM(comprimento_total_mm) FROM resumo_barras")
        tot_util, tot_bruto = cursor.fetchone()
        fracao_aproveitamento = Fraction(tot_util, tot_bruto)
        print(f"  • Aproveitamento Global Auditado: {tot_util} mm / {tot_bruto} mm ({float(fracao_aproveitamento*100):.2f}%)")

        print("=== Auditoria Independente APROVADA com 100% de sucesso! ===")
        return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditor independente de plano de corte 1D.")
    parser.add_argument("arquivo_zip", nargs="?", default="", help="Caminho do pacote ZIP a ser auditado (opcional)")
    args = parser.parse_args()

    if args.arquivo_zip:
        sucesso = verificar_pacote_zip(Path(args.arquivo_zip))
        return 0 if sucesso else 1

    import subprocess
    print("Nenhum arquivo ZIP fornecido. Gerando pacote de demonstração para auto-auditoria...")
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "exemplo-corte.zip"
        cmd = [
            sys.executable,
            "-m",
            "plano_corte_barras",
            "processar",
            "-i",
            "exemplos/estrutura_metalica_galpao.json",
            "-z",
            str(zip_path),
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        env["PYTHONIOENCODING"] = "utf-8"
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[ERRO] Falha ao gerar pacote de demonstração: {res.stderr}", file=sys.stderr)
            return 1
        sucesso = verificar_pacote_zip(zip_path)
        return 0 if sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
