# Verificação Independente e Prova Matemática — plano-corte-barras

Este documento detalha os fundamentos da conservação milimétrica e a auditoria independente do **plano-corte-barras**.

---

## 1. Identidade de Conservação Milimétrica

Em qualquer plano de corte físico, para cada barra $b$ selecionada do estoque, a soma dos elementos longitudinais deve ser rigorosamente igual ao comprimento total inicial da barra:

$$\text{comprimento\_total}_b \equiv \text{refugo\_ponta}_b + \sum_{p \in \text{pecas}_b} (\text{comprimento}_p + \text{perda\_kerf}_p) + \text{sobra\_final}_b$$

Onde:
- $\text{refugo\_ponta}_b$: Margem eliminada no primeiro corte para regularização do topo/esquadro da barra bruta.
- $\text{comprimento}_p$: Comprimento útil final da peça cortada.
- $\text{perda\_kerf}_p$: Espessura física do disco de corte / serra de fita consumida em cavacos.
- $\text{sobra\_final}_b$: Comprimento residual remanescente na barra após todos os cortes.

Se $\text{sobra\_final}_b \ge \text{comprimento\_minimo\_aproveitavel}$, a sobra é classificada como **retalho aproveitável** e pode ser reincorporada ao estoque de sobras; caso contrário, é classificada como **sucata descartável**.

---

## 2. Invariante de Atendimento da Demanda

O motor assegura que a lista de cortes atende de forma biunívoca a todas as peças solicitadas:

$$\forall (id, perfil, comp) \in \text{demandas}: \quad \text{quantidade\_cortada} \equiv \text{quantidade\_solicitada}$$

Nenhuma peça pode faltar, e nenhuma peça excedente pode ser cortada.

---

## 3. Auditoria Relacional com `tools/verify_independent.py`

O script autônomo `tools/verify_independent.py` audita o arquivo ZIP gerado sem importar o código-fonte da aplicação:

1. **Conferência de Hash:** Recalcula o SHA-256 de todos os artefatos do pacote e confronta com o `SHA256SUMS`.
2. **Carga em SQLite em Memória:** Insere `plano-corte.csv` e `resumo-barras.csv` em tabelas relacionais.
3. **Auditoria de Conservação Barra a Barra:** Valida por consulta SQL que a soma de refugo, peças, kerf e sobra é igual ao comprimento da barra para 100% das barras.
4. **Auditoria de Alinhamento Geométrico:** Confere que as peças estão perfeitamente contíguas, sem sobreposição nem saltos espaciais.
5. **Auditoria da Demanda:** Agrupa as peças cortadas e confronta com `entrada.json`.
6. **Aproveitamento Racional:** Calcula a fração racional exata do aproveitamento global.
