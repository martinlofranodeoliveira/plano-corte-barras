# Guia de Interoperabilidade — plano-corte-barras

Este documento orienta a integração do **plano-corte-barras** com sistemas de PCP (Planejamento e Controle da Produção), ERPs industriais e planilhas eletrônicas.

---

## 1. Integração com PCP e ERP Industrial

O artefato `plano.json` disponibiliza a estrutura completa do lote otimizado:
- Barras de estoque consumidas com custos e IDs de rastreabilidade.
- Sequência ordenada de cortes com posições milimétricas.
- Metadados de retalhos que podem ser retornados ao inventário como sobras aproveitáveis.

```python
import json
from pathlib import Path

dados = json.loads(Path("plano.json").read_text(encoding="utf-8"))
for b in dados["barras_cortadas"]:
    if b["tipo_sobra"] == "APROVEITAVEL":
        print(f"Retalho para reestocar: Perfil {b['perfil']}, {b['sobra_final_mm']} mm")
```

---

## 2. Emissão de Roteiros de Chão de Fábrica

O arquivo `lista-corte.md` pode ser impresso diretamente ou disponibilizado em tablets industriais para o operador de serra:
- Tabela com sequência exata de cortes.
- Posição inicial e final de cada peça na escala métrica da máquina.
- Destaque visual da espessura de corte e refugo de ponta.

---

## 3. Segurança em Planilhas Eletrônicas

Os arquivos `plano-corte.csv` e `resumo-barras.csv` possuem proteção ativa contra injeção de fórmulas (*CSV Injection*). Qualquer campo que comece com `=`, `+`, `-`, `@`, `\t` ou `\r` é automaticamente protegido com `'`.
