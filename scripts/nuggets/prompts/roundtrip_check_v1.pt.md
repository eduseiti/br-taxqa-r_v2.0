Você recebe uma pergunta sobre o Imposto sobre a Renda da Pessoa Física (IRPF), a **resposta oficial** e uma **reconstrução** dessa resposta, escrita por outra pessoa sem ver a resposta oficial. Liste os fatos da resposta oficial que **faltam** na reconstrução ou que nela aparecem **alterados** (outro valor, outra data, outro período, condição ou exceção perdida, quantificador trocado, veredito oposto).

Não liste:

- diferenças de redação, de ordem ou de organização;
- remissões a outras perguntas ("ver pergunta 123") nem números que aparecem só em exemplos de cálculo ilustrativos;
- a falta de menção explícita ao exercício de 2024 ou ao ano-calendário de 2023.

Para cada fato listado, dê:

- `source_span`: o trecho **literal** da resposta oficial que contém o fato (uma frase ou um item), copiado sem alterações;
- `problem`: `missing` (o fato não aparece) ou `altered` (aparece com alguma diferença de conteúdo);
- `description`: uma frase curta dizendo o que falta ou o que mudou.

Se nada falta, devolva uma lista vazia.

Formato de saída (somente o JSON):

```json
{"missing": [{"source_span": "...", "problem": "missing|altered", "description": "..."}]}
```
