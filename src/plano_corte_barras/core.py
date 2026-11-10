"""Motor de cálculo e otimização determinística de plano de corte unidimensional (1D)."""

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple

from .errors import (
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


def formatar_fracao_percentual(fracao: Fraction, casas: int = 2) -> str:
    """Formata fração racional em percentual com casas decimais via aritmética inteira exata."""
    if fracao.denominator == 0:
        return "0,00%"
    fator = 10 ** casas
    numerador_ampliado = fracao.numerator * 100 * fator
    denominador = fracao.denominator
    inteiro = numerador_ampliado // denominador
    resto = numerador_ampliado % denominador
    if resto * 2 >= denominador:
        inteiro += 1
    parte_inteira = inteiro // fator
    parte_decimal = inteiro % fator
    return f"{parte_inteira},{parte_decimal:0{casas}d}%"


def formatar_moeda_centavos(centavos: int) -> str:
    """Formata valor inteiro em centavos para moeda brasileira (R$ X.XXX,XX)."""
    negativo = centavos < 0
    centavos_abs = abs(centavos)
    reais = centavos_abs // 100
    resto = centavos_abs % 100
    reais_formatados = f"{reais:,}".replace(",", ".")
    sinal = "-" if negativo else ""
    return f"{sinal}R$ {reais_formatados},{resto:02d}"


@dataclass(frozen=True)
class BarraEstoque:
    id: str
    perfil: str
    comprimento_mm: int
    quantidade: int
    custo_unitario_centavos: int = 0


@dataclass(frozen=True)
class PecaDemanda:
    id: str
    perfil: str
    comprimento_mm: int
    quantidade: int
    descricao: str = ""


@dataclass(frozen=True)
class PecaCortada:
    peca_id: str
    descricao: str
    comprimento_mm: int
    posicao_inicio_mm: int
    posicao_fim_mm: int
    perda_corte_mm: int


@dataclass
class BarraCortada:
    indice_barra: int
    barra_estoque_id: str
    perfil: str
    comprimento_total_mm: int
    custo_unitario_centavos: int
    refugo_ponta_mm: int
    pecas: List[PecaCortada] = field(default_factory=list)
    sobra_final_mm: int = 0
    tipo_sobra: str = "SUCATA"  # "APROVEITAVEL" ou "SUCATA"

    @property
    def comprimento_util_pecas_mm(self) -> int:
        return sum(p.comprimento_mm for p in self.pecas)

    @property
    def perda_cortes_total_mm(self) -> int:
        return sum(p.perda_corte_mm for p in self.pecas)

    @property
    def taxa_aproveitamento(self) -> Fraction:
        if self.comprimento_total_mm == 0:
            return Fraction(0, 1)
        return Fraction(self.comprimento_util_pecas_mm, self.comprimento_total_mm)


@dataclass
class ResumoGlobal:
    total_barras_utilizadas: int
    total_comprimento_bruto_mm: int
    total_comprimento_util_mm: int
    total_perda_cortes_mm: int
    total_refugo_ponta_mm: int
    total_sobra_aproveitavel_mm: int
    total_sucata_descarte_mm: int
    total_custo_centavos: int
    aproveitamento_global_fracao: Fraction
    aproveitamento_global_percentual: str
    perda_global_percentual: str


@dataclass
class ResultadoOtimizacao:
    projeto_nome: str
    espessura_corte_mm: int
    comprimento_minimo_aproveitavel_mm: int
    margem_seguranca_ponta_mm: int
    barras_cortadas: List[BarraCortada]
    resumo_global: ResumoGlobal
    pecas_demandadas: List[PecaDemanda]
    barras_estoque: List[BarraEstoque]


def otimizar_plano_corte(dados: dict) -> ResultadoOtimizacao:
    """Valida a entrada e executa a otimização combinatória determinística de corte 1D."""
    if not isinstance(dados, dict):
        raise ErroValidacaoEntrada(ERR_VALOR_INVALIDO, "Dados de entrada devem ser um objeto JSON.")

    projeto_info = dados.get("projeto", {})
    projeto_nome = str(projeto_info.get("nome", "Plano de Corte 1D"))

    # Parâmetros operacionais
    parametros = dados.get("parametros", {})
    espessura_corte_mm = parametros.get("espessura_corte_mm", 3)
    comprimento_minimo_aproveitavel_mm = parametros.get("comprimento_minimo_aproveitavel_mm", 300)
    margem_seguranca_ponta_mm = parametros.get("margem_seguranca_ponta_mm", 0)

    if not isinstance(espessura_corte_mm, int) or espessura_corte_mm < 0:
        raise ErroValidacaoEntrada(ERR_PARAMETRO_INVALIDO, f"Espessura do corte inválida: {espessura_corte_mm} mm.")
    if not isinstance(comprimento_minimo_aproveitavel_mm, int) or comprimento_minimo_aproveitavel_mm < 0:
        raise ErroValidacaoEntrada(ERR_PARAMETRO_INVALIDO, f"Comprimento mínimo de sobra aproveitável inválido: {comprimento_minimo_aproveitavel_mm} mm.")
    if not isinstance(margem_seguranca_ponta_mm, int) or margem_seguranca_ponta_mm < 0:
        raise ErroValidacaoEntrada(ERR_PARAMETRO_INVALIDO, f"Margem de ponta inválida: {margem_seguranca_ponta_mm} mm.")

    # 1. Validação do Estoque de Barras
    raw_estoque = dados.get("estoque_barras")
    if not raw_estoque or not isinstance(raw_estoque, list):
        raise ErroValidacaoEntrada(ERR_ESTOQUE_VAZIO, "O estoque de barras é obrigatório e não pode estar vazio.")

    barras_estoque: List[BarraEstoque] = []
    for idx, b_data in enumerate(raw_estoque):
        if not isinstance(b_data, dict):
            raise ErroValidacaoEntrada(ERR_ESTOQUE_VAZIO, f"Barra de estoque no índice {idx} inválida.")
        bid = str(b_data.get("id", f"BARRA-{idx+1}")).strip()
        perfil = str(b_data.get("perfil", "PADRAO")).strip().upper()
        comp = b_data.get("comprimento_mm")
        qtd = b_data.get("quantidade", 1)
        custo = b_data.get("custo_unitario_centavos", 0)

        if not isinstance(comp, int) or comp <= 0:
            raise ErroValidacaoEntrada(ERR_COMPRIMENTO_INVALIDO, f"Comprimento da barra '{bid}' inválido: {comp}.")
        if not isinstance(qtd, int) or qtd <= 0:
            raise ErroValidacaoEntrada(ERR_QUANTIDADE_INVALIDA, f"Quantidade da barra '{bid}' inválida: {qtd}.")
        if not isinstance(custo, int) or custo < 0:
            raise ErroValidacaoEntrada(ERR_VALOR_INVALIDO, f"Custo da barra '{bid}' inválido: {custo}.")

        barras_estoque.append(BarraEstoque(
            id=bid,
            perfil=perfil,
            comprimento_mm=comp,
            quantidade=qtd,
            custo_unitario_centavos=custo,
        ))

    # 2. Validação da Demanda de Peças
    raw_demanda = dados.get("pecas_demandadas")
    if not raw_demanda or not isinstance(raw_demanda, list):
        raise ErroValidacaoEntrada(ERR_DEMANDA_VAZIA, "A demanda de peças é obrigatória e não pode estar vazia.")

    pecas_demanda: List[PecaDemanda] = []
    for idx, p_data in enumerate(raw_demanda):
        if not isinstance(p_data, dict):
            raise ErroValidacaoEntrada(ERR_DEMANDA_VAZIA, f"Peça no índice {idx} inválida.")
        pid = str(p_data.get("id", f"PECA-{idx+1}")).strip()
        perfil = str(p_data.get("perfil", "PADRAO")).strip().upper()
        comp = p_data.get("comprimento_mm")
        qtd = p_data.get("quantidade", 1)
        desc = str(p_data.get("descricao", pid)).strip()

        if not isinstance(comp, int) or comp <= 0:
            raise ErroValidacaoEntrada(ERR_COMPRIMENTO_INVALIDO, f"Comprimento da peça '{pid}' inválido: {comp}.")
        if not isinstance(qtd, int) or qtd <= 0:
            raise ErroValidacaoEntrada(ERR_QUANTIDADE_INVALIDA, f"Quantidade da peça '{pid}' inválida: {qtd}.")

        pecas_demanda.append(PecaDemanda(
            id=pid,
            perfil=perfil,
            comprimento_mm=comp,
            quantidade=qtd,
            descricao=desc,
        ))

    # Agrupa por perfil de material
    perfis_demanda = set(p.perfil for p in pecas_demanda)
    perfis_estoque = set(b.perfil for b in barras_estoque)

    perfis_faltantes = perfis_demanda - perfis_estoque
    if perfis_faltantes:
        raise ErroValidacaoEntrada(
            ERR_PERFIL_INCOMPATIVEL,
            f"Perfis demandados não existentes no estoque de barras: {perfis_faltantes}.",
        )

    # Executa otimização por perfil de forma determinística
    todas_barras_cortadas: List[BarraCortada] = []
    indice_global_barra = 1

    for perfil in sorted(perfis_demanda):
        barras_perfil = [b for b in barras_estoque if b.perfil == perfil]
        pecas_perfil = [p for p in pecas_demanda if p.perfil == perfil]

        # Comprimento máximo útil disponível em uma barra
        comp_max_util = max(b.comprimento_mm - margem_seguranca_ponta_mm for b in barras_perfil)
        for p in pecas_perfil:
            if p.comprimento_mm > comp_max_util:
                raise ErroInviavel(
                    ERR_PECA_MAIOR_QUE_BARRA,
                    f"A peça '{p.id}' ({p.comprimento_mm} mm) do perfil '{perfil}' excede o comprimento útil máximo ({comp_max_util} mm) das barras disponíveis.",
                )

        # Expansão individual de peças a cortar
        # Tupla: (peca_id, comprimento_mm, descricao)
        itens_a_cortar: List[Tuple[str, int, str]] = []
        for p in pecas_perfil:
            for _ in range(p.quantidade):
                itens_a_cortar.append((p.id, p.comprimento_mm, p.descricao))

        # Ordenação FFD: maior comprimento primeiro; desempate pelo ID
        itens_a_cortar.sort(key=lambda item: (-item[1], item[0]))

        # Pool de barras de estoque expandidas disponíveis
        pool_barras: List[BarraEstoque] = []
        for b in sorted(barras_perfil, key=lambda b: (-b.comprimento_mm, b.custo_unitario_centavos, b.id)):
            for _ in range(b.quantidade):
                pool_barras.append(b)

        # Alocação Best-Fit Decreasing (BFD)
        # Cada barra ativa armazena:
        # [barra_estoque, espaco_restante_mm, lista_pecas[(peca_id, comp, desc)]]
        barras_ativas: List[Dict[str, Any]] = []

        for p_id, p_comp, p_desc in itens_a_cortar:
            melhor_indice = -1
            menor_desperdicio = None

            # Tenta encaixar em barra já aberta
            for b_idx, b_ativa in enumerate(barras_ativas):
                custo_espaco = p_comp if not b_ativa["pecas"] else (espessura_corte_mm + p_comp)
                if b_ativa["espaco_restante_mm"] >= custo_espaco:
                    desperdicio_apos = b_ativa["espaco_restante_mm"] - custo_espaco
                    if menor_desperdicio is None or desperdicio_apos < menor_desperdicio:
                        menor_desperdicio = desperdicio_apos
                        melhor_indice = b_idx

            if melhor_indice != -1:
                # Encaixa na melhor barra existente
                b_ativa = barras_ativas[melhor_indice]
                custo_espaco = p_comp if not b_ativa["pecas"] else (espessura_corte_mm + p_comp)
                b_ativa["espaco_restante_mm"] -= custo_espaco
                b_ativa["pecas"].append((p_id, p_comp, p_desc))
            else:
                # Abre nova barra do pool
                if not pool_barras:
                    raise ErroInviavel(
                        ERR_ESTOQUE_INSUFICIENTE,
                        f"Estoque insuficiente de barras para o perfil '{perfil}'. Faltaram peças a cortar.",
                    )
                # Seleciona barra do pool que melhor atende o item (menor resto inicial)
                idx_pool_escolhido = -1
                menor_sobra_pool = None
                for idx_p, b_cand in enumerate(pool_barras):
                    capacidade_util = b_cand.comprimento_mm - margem_seguranca_ponta_mm
                    if capacidade_util >= p_comp:
                        sobra_cand = capacidade_util - p_comp
                        if menor_sobra_pool is None or sobra_cand < menor_sobra_pool:
                            menor_sobra_pool = sobra_cand
                            idx_pool_escolhido = idx_p

                if idx_pool_escolhido == -1:
                    raise ErroInviavel(
                        ERR_ESTOQUE_INSUFICIENTE,
                        f"Nenhuma barra disponível no estoque suporta a peça '{p_id}' ({p_comp} mm).",
                    )

                barra_escolhida = pool_barras.pop(idx_pool_escolhido)
                capacidade_util = barra_escolhida.comprimento_mm - margem_seguranca_ponta_mm
                barras_ativas.append({
                    "barra_estoque": barra_escolhida,
                    "espaco_restante_mm": capacidade_util - p_comp,
                    "pecas": [(p_id, p_comp, p_desc)],
                })

        # Montagem dos objetos BarraCortada e cálculo exato das posições de corte
        for b_ativa in barras_ativas:
            b_est = b_ativa["barra_estoque"]
            pecas_alocadas = b_ativa["pecas"]

            posicao_atual = margem_seguranca_ponta_mm
            pecas_cortadas_obj: List[PecaCortada] = []

            for i, (p_id, p_comp, p_desc) in enumerate(pecas_alocadas):
                pos_inicio = posicao_atual
                pos_fim = pos_inicio + p_comp
                # Perda do corte entre peças (apenas se houver corte subsequente ou sobra)
                perda = espessura_corte_mm if (i < len(pecas_alocadas) - 1 or b_ativa["espaco_restante_mm"] > 0) else 0

                pecas_cortadas_obj.append(PecaCortada(
                    peca_id=p_id,
                    descricao=p_desc,
                    comprimento_mm=p_comp,
                    posicao_inicio_mm=pos_inicio,
                    posicao_fim_mm=pos_fim,
                    perda_corte_mm=perda,
                ))
                posicao_atual = pos_fim + perda

            sobra_final = b_est.comprimento_mm - posicao_atual
            tipo_sobra = "APROVEITAVEL" if sobra_final >= comprimento_minimo_aproveitavel_mm else "SUCATA"

            barra_cortada = BarraCortada(
                indice_barra=indice_global_barra,
                barra_estoque_id=b_est.id,
                perfil=perfil,
                comprimento_total_mm=b_est.comprimento_mm,
                custo_unitario_centavos=b_est.custo_unitario_centavos,
                refugo_ponta_mm=margem_seguranca_ponta_mm,
                pecas=pecas_cortadas_obj,
                sobra_final_mm=sobra_final,
                tipo_sobra=tipo_sobra,
            )

            # Verificação estrita da conservação de comprimento:
            # refugo_ponta + sum(p.comprimento + p.perda) + sobra_final == comprimento_total
            total_verificacao = (
                barra_cortada.refugo_ponta_mm
                + sum(p.comprimento_mm + p.perda_corte_mm for p in barra_cortada.pecas)
                + barra_cortada.sobra_final_mm
            )
            if total_verificacao != barra_cortada.comprimento_total_mm:
                raise ErroValidacaoEntrada(
                    ERR_COMPRIMENTO_INVALIDO,
                    f"Falha de conservação de comprimento na barra {indice_global_barra}: {total_verificacao} != {barra_cortada.comprimento_total_mm}.",
                )

            todas_barras_cortadas.append(barra_cortada)
            indice_global_barra += 1

    # 3. Consolidação dos Resultados Globais
    total_barras_utilizadas = len(todas_barras_cortadas)
    total_bruto = sum(b.comprimento_total_mm for b in todas_barras_cortadas)
    total_util = sum(b.comprimento_util_pecas_mm for b in todas_barras_cortadas)
    total_perda_cortes = sum(b.perda_cortes_total_mm for b in todas_barras_cortadas)
    total_refugo_ponta = sum(b.refugo_ponta_mm for b in todas_barras_cortadas)
    total_sobra_aproveitavel = sum(b.sobra_final_mm for b in todas_barras_cortadas if b.tipo_sobra == "APROVEITAVEL")
    total_sucata_descarte = sum(b.sobra_final_mm for b in todas_barras_cortadas if b.tipo_sobra == "SUCATA")
    total_custo = sum(b.custo_unitario_centavos for b in todas_barras_cortadas)

    fracao_aprov = Fraction(total_util, total_bruto) if total_bruto > 0 else Fraction(0, 1)
    fracao_perda = Fraction(total_bruto - total_util, total_bruto) if total_bruto > 0 else Fraction(0, 1)

    resumo = ResumoGlobal(
        total_barras_utilizadas=total_barras_utilizadas,
        total_comprimento_bruto_mm=total_bruto,
        total_comprimento_util_mm=total_util,
        total_perda_cortes_mm=total_perda_cortes,
        total_refugo_ponta_mm=total_refugo_ponta,
        total_sobra_aproveitavel_mm=total_sobra_aproveitavel,
        total_sucata_descarte_mm=total_sucata_descarte,
        total_custo_centavos=total_custo,
        aproveitamento_global_fracao=fracao_aprov,
        aproveitamento_global_percentual=formatar_fracao_percentual(fracao_aprov, casas=2),
        perda_global_percentual=formatar_fracao_percentual(fracao_perda, casas=2),
    )

    return ResultadoOtimizacao(
        projeto_nome=projeto_nome,
        espessura_corte_mm=espessura_corte_mm,
        comprimento_minimo_aproveitavel_mm=comprimento_minimo_aproveitavel_mm,
        margem_seguranca_ponta_mm=margem_seguranca_ponta_mm,
        barras_cortadas=todas_barras_cortadas,
        resumo_global=resumo,
        pecas_demandadas=pecas_demanda,
        barras_estoque=barras_estoque,
    )
