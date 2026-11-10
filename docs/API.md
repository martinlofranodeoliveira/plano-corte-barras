# Documentação da API Python — plano-corte-barras

O pacote pode ser consumido diretamente em código Python 3.11+.

---

## 1. Importação Principal

```python
from plano_corte_barras import (
    otimizar_plano_corte,
    decodificar_json_estrito,
    codificar_json_canonico,
    formatar_fracao_percentual,
    formatar_moeda_centavos,
    ResultadoOtimizacao,
    BarraCortada,
    PecaCortada,
    ResumoGlobal,
)
```

---

## 2. Funções Principais

### `otimizar_plano_corte(dados: dict) -> ResultadoOtimizacao`
Executa o algoritmo determinístico de *1D Cutting Stock / Bin Packing* e retorna o plano de corte estruturado.

```python
entrada = {
    "projeto": {"nome": "Serralheria"},
    "parametros": {"espessura_corte_mm": 3, "margem_seguranca_ponta_mm": 10},
    "estoque_barras": [
        {"id": "B6M", "perfil": "TUBO", "comprimento_mm": 6000, "quantidade": 10, "custo_unitario_centavos": 15000}
    ],
    "pecas_demandadas": [
        {"id": "P1", "perfil": "TUBO", "comprimento_mm": 2000, "quantidade": 5}
    ]
}

resultado = otimizar_plano_corte(entrada)
print(f"Barras usadas: {resultado.resumo_global.total_barras_utilizadas}")
print(f"Aproveitamento: {resultado.resumo_global.aproveitamento_global_percentual}")
```

### `formatar_fracao_percentual(fracao: Fraction, casas: int = 2) -> str`
Converte qualquer fração racional para percentual com arredondamento padrão e aritmética inteira exata:
```python
from fractions import Fraction
formatar_fracao_percentual(Fraction(8935, 10000))  # "89,35%"
```

### `formatar_moeda_centavos(centavos: int) -> str`
Converte centavos inteiros para formato monetário BRL:
```python
formatar_moeda_centavos(25400)  # "R$ 254,00"
```
