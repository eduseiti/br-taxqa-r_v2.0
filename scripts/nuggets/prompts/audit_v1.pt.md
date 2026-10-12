Você é um revisor de **nuggets** extraídos da resposta oficial a uma pergunta do documento "Perguntas e Respostas IRPF 2024" (Receita Federal, exercício de 2024, ano-calendário de 2023). Os nuggets são afirmações curtas, autocontidas e atômicas, usadas para avaliar respostas geradas por sistemas automáticos. A resposta oficial é a verdade por definição: compare os nuggets **com a resposta oficial**, nunca com a legislação que você conhece.

## Diretrizes que os nuggets deviam seguir

- Cada nugget é compreensível sem a pergunta e sem a resposta: nomeia quem, o tributo ou a declaração e, quando a regra depende dele, o período. Se a resposta não indica o período, o nugget pode usar o da pergunta ou o do documento (exercício de 2024, ano-calendário de 2023); isso **não** é um erro.
- Uma condição, exceção ou requisito fica no mesmo nugget que a regra que limita. Há um nugget por item ou subitem enumerado da resposta; objetos listados dentro de uma mesma frase ou item (e listas ilustrativas: "etc.", "tais como", "por exemplo") ficam em um só nugget, salvo se a resposta lhes der tratamentos diferentes.
- Valores, datas, percentuais, quantificadores ("somente", "até", "qualquer", "todos") e termos técnicos são copiados literalmente. Citações legais ficam fora do texto do nugget.
- Remissões que apenas delegam o tratamento a outra pergunta ("ver pergunta 123") **não** geram nugget; números que aparecem só em exemplos de cálculo ilustrativos também não. Notas "Atenção" geram nuggets, normalmente `okay`.
- `vital` = uma resposta correta a esta pergunta precisa conter o fato; `okay` = útil, mas não indispensável.

## O que verificar

Para **cada nugget**, na ordem dada, responda `true` (passa) ou `false` (falha):

- `c1_faithful` — a resposta oficial (lida com a pergunta) diz isso, sem nada acrescentado, removido ou alterado? Falha se um valor, data ou percentual difere; se o veredito Sim/Não está invertido; se um quantificador ou o alcance muda; se um termo técnico foi trocado por um quase-sinônimo; se uma condição ou exceção da mesma frase foi perdida; se afirma algo que a resposta não diz.
- `c2_self_contained` — alguém que não viu a pergunta nem a resposta entende e consegue verificar o nugget? Falha com "esse", "tal", "o referido" sem referente, ou "o contribuinte" genérico quando a pergunta delimita de quem se trata.
- `c3_one_unit` — uma resposta de sistema pode acertá-lo ou errá-lo por inteiro? Falha se junta dois fatos independentes (deveria ser dividido) ou se é um fragmento sem sentido sozinho (deveria ser unido a outro).
- `c4_importance` — o rótulo `vital`/`okay` está correto segundo a definição acima?

Quando algum item falhar, explique em `problem` o defeito e, em `fix`, a correção (o texto corrigido do nugget, a divisão sugerida ou o rótulo correto). Quando todos passarem, deixe `problem` e `fix` vazios.

Para a **resposta como um todo**:

- `omissions` (C5) — fatos da resposta oficial que **nenhum** nugget cobre, exceto remissões e exemplos numéricos. Para cada um, dê o `source_span` (o trecho **literal** da resposta oficial, copiado sem alterações) e o `fact` (o nugget que faltou, já redigido). Você recebe também uma lista de **candidatos a omissão** encontrados por outros métodos automáticos; confirme somente os que forem de fato omissões, e acrescente outros que encontrar.
- `redundant` (C6) — pares de nuggets que carregam o **mesmo** fato.

Seja rigoroso, mas não aponte preferências de estilo: aponte apenas defeitos que mudariam a avaliação de uma resposta de sistema.

Formato de saída (somente o JSON):

```json
{"nuggets": [{"nugget": 1, "c1_faithful": true, "c2_self_contained": true, "c3_one_unit": true, "c4_importance": true, "problem": "", "fix": ""}],
 "omissions": [{"source_span": "...", "fact": "..."}],
 "redundant": [{"a": 1, "b": 2}]}
```
