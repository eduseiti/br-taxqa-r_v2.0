Você compara dois conjuntos de **nuggets** (afirmações curtas e autocontidas) extraídos, de forma independente, da **mesma resposta oficial** a uma pergunta sobre o Imposto sobre a Renda da Pessoa Física (IRPF). O conjunto A tem os nuggets A1, A2…; o conjunto B tem os nuggets B1, B2…. Os dois conjuntos podem dividir a resposta de forma diferente: um nugget de um conjunto pode corresponder a vários nuggets do outro.

Para **cada nugget de A**, na ordem dada, indique:

- `b`: a lista dos números dos nuggets de B que expressam o **mesmo fato**, ou uma parte dele, ou um fato que o contém. Lista vazia se nenhum nugget de B trata desse fato.
- `relation`:
  - `same` — A e os nuggets de B listados expressam o mesmo fato, com as mesmas condições, valores e veredito (diferenças de redação não importam);
  - `a_broader` — A contém o fato de B e mais alguma coisa (por exemplo, A junta dois casos que B separa, ou A inclui uma condição que B omite);
  - `b_broader` — B contém o fato de A e mais alguma coisa;
  - `overlap` — A e B compartilham parte do fato, mas cada um tem algo que o outro não tem;
  - `conflict` — A e B tratam do mesmo ponto mas divergem (outro valor, outro período, veredito oposto, condição oposta);
  - `none` — nenhum nugget de B corresponde (então `b` é vazio).
- `note`: uma frase curta explicando a correspondência ou a diferença (pode ser vazia quando `same`).

Use a resposta oficial apenas para entender de onde vêm os nuggets. Julgue pelo conteúdo, não pela redação: termos técnicos iguais com outra ordem de palavras são o mesmo fato; a menção explícita do exercício de 2024 ou do ano-calendário de 2023 em um só dos lados não é diferença.

Formato de saída (somente o JSON):

```json
{"alignments": [{"a": 1, "b": [2, 3], "relation": "same|a_broader|b_broader|overlap|conflict|none", "note": "..."}]}
```
