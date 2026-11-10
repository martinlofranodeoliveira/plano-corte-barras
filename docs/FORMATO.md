# Especificação de Formato — plano-corte-barras

Este documento descreve os esquemas de entrada e saída do **plano-corte-barras**.

---

## 1. Entrada Canônica (JSON UTF-8)

O arquivo de entrada deve ser codificado em **UTF-8 estrito** sem BOM (*Byte Order Mark*), tamanho máximo de 10 MiB e profundidade máxima de 32 níveis. Valores dimensionais devem ser expressos estritamente em **milímetros inteiros** (`int` > 0), quantidades em inteiros (`int` > 0) e custos em **centavos inteiros** (`int` >= 0). Números de ponto flutuante (`float`) são terminantemente proibidos e causam a rejeição com código `JSON_FLOAT_PROIBIDO`.

### Estrutura Raiz

```json
{
  "projeto": {
    "nome": "string (obrigatório)"
  },
  "parametros": {
    "espessura_corte_mm": "int >= 0 (padrão: 3)",
    "comprimento_minimo_aproveitavel_mm": "int >= 0 (padrão: 300)",
    "margem_seguranca_ponta_mm": "int >= 0 (padrão: 0)"
  },
  "estoque_barras": [
    {
      "id": "string (identificador da barra no estoque)",
      "perfil": "string (identificador do tipo de perfil / material)",
      "comprimento_mm": "int > 0 (comprimento bruto da barra)",
      "quantidade": "int > 0 (número de barras disponíveis)",
      "custo_unitario_centavos": "int >= 0 (custo de aquisição por barra)"
    }
  ],
  "pecas_demandadas": [
    {
      "id": "string (identificador da peça na lista de corte)",
      "perfil": "string (deve corresponder a um perfil disponível)",
      "comprimento_mm": "int > 0 (comprimento acabado da peça)",
      "quantidade": "int > 0 (número de peças demandadas)",
      "descricao": "string (opcional, descrição do elemento estrutural)"
    }
  ]
}
```

---

## 2. Artefatos de Saída

Ao executar o comando `processar`, são gerados:

1. `plano-corte.csv`: Sequência de corte milimétrica com posição inicial, posição final, kerf e identificação de peça.
2. `resumo-barras.csv`: Totais por barra bruta (comprimento útil, perdas de corte, sobra final, classificação aproveitável/sucata e percentual de aproveitamento).
3. `lista-corte.md`: Roteiro de oficina formatado para acompanhamento do operador da serra.
4. `diagrama-corte.svg`: Painel vetorial analítico (1440×900) ilustrando o leiaute físico de cada barra.
5. `plano.json`: Memória de cálculo estruturada para integração com PCP e ERP.
6. `SHA256SUMS`: Manifesto criptográfico de integridade.
7. `exemplo-corte.zip`: Pacote ZIP determinístico com garantia de não sobrescrita atômica.
