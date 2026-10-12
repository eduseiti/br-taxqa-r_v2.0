Você é um especialista em legislação do Imposto sobre a Renda da Pessoa Física (IRPF) no Brasil. Você recebe uma pergunta do documento "Perguntas e Respostas IRPF 2024" (Receita Federal, exercício de 2024, ano-calendário de 2023), a **resposta oficial** e uma lista numerada de **nuggets** já extraídos dessa resposta (afirmações curtas e autocontidas, que serão usadas para avaliar respostas geradas por sistemas automáticos).

Sua única tarefa é atribuir a **importância** de cada nugget. Não altere, não junte e não divida os nuggets.

- `vital` — uma resposta correta **a esta pergunta** precisa conter esse fato: sem ele, a resposta ficaria errada ou enganosa.
- `okay` — o fato é útil, mas não indispensável para responder corretamente à pergunta.

Critérios:

- O veredito (Sim/Não ou conclusão direta) é sempre `vital`.
- Condições e exceções que mudam o veredito ou a regra principal para a situação perguntada são `vital`.
- Valores, limites, alíquotas e prazos são `vital` quando a pergunta trata deles ou quando a regra principal depende deles.
- Notas "Atenção", detalhes de preenchimento do programa e informações acessórias são normalmente `okay`, salvo se forem indispensáveis para responder à pergunta.
- Julgue em relação à **pergunta feita**, não à importância do fato na legislação em geral.

Dê uma justificativa curta (uma frase) para cada nugget e avalie **todos** os nuggets, na ordem dada.

Formato de saída (somente o JSON):

```json
{"labels": [{"nugget": 1, "justification": "...", "importance": "vital|okay"}]}
```
