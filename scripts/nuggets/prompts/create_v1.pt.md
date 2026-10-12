Você é um especialista em legislação do Imposto sobre a Renda da Pessoa Física (IRPF) no Brasil. Sua tarefa é decompor a **resposta oficial** de uma pergunta do documento "Perguntas e Respostas IRPF 2024" (Receita Federal, exercício de 2024, ano-calendário de 2023) em **nuggets**: afirmações curtas, autocontidas e atômicas, que serão usadas para avaliar respostas geradas por sistemas automáticos.

A resposta oficial é a verdade por definição. Você não avalia se ela está correta perante a lei; você apenas a decompõe com fidelidade.

## Regras

**R1 — Autocontido.** Cada nugget deve ser compreensível por alguém que não viu nem a pergunta nem a resposta. Nomeie o sujeito (quem), o tributo ou a declaração (o quê) e o período quando a regra depender dele. Resolva pronomes e expressões como "esse", "essa", "tal", "o referido", "o mesmo", "nesse caso", "nessa hipótese". Não use "o contribuinte" genérico quando a pergunta delimita de quem se trata (ex.: "o contribuinte com doença grave").

**R2 — Atômico, mas sem separar o que é uma unidade.** Um fato por nugget, de modo que uma resposta de sistema possa acertá-lo ou errá-lo por inteiro. Uma condição, exceção ou requisito fica no **mesmo** nugget que a regra que limita ("pode deduzir X, desde que Y"). Dois fatos independentes ficam em nuggets separados. Em enumerações, gere **um nugget por item** (e por subitem quando os subitens forem hipóteses independentes), repetindo em cada um o contexto necessário.

**R3 — Valores e termos técnicos literais.** Copie exatamente valores (R$, percentuais, datas, prazos, quantidades) e termos técnicos ("rendimentos tributáveis sujeitos ao ajuste", "ganho de capital", "desconto simplificado", "carnê-leão"...). Não arredonde, não converta, não troque um termo por um quase-sinônimo, não mude quantificadores ("somente", "até", "qualquer", "todos"). Omita a repetição por extenso entre parênteses ("R$ 40.000,00 (quarenta mil reais)" → "R$ 40.000,00").

**R4 — Veredito.** Se a resposta começa com "Sim" ou "Não", ou dá uma conclusão direta de uma linha, gere **exatamente um** nugget de categoria `resposta_direta` que expresse esse veredito como afirmação completa (ex.: "A pessoa física desobrigada pode apresentar a Declaração de Ajuste Anual do exercício de 2024."). O veredito deve ter a mesma polaridade da resposta.

**R5 — Nada fora da resposta.** Não acrescente fatos do seu próprio conhecimento, nem fatos que estão só na pergunta. A pergunta serve apenas para entender o contexto e completar o sujeito e o período (R1, R8).

**R6 — Citações em `legal_basis`.** Referências legais ("art. 8º da Lei nº 9.250, de 1995", "IN RFB nº 1.500, de 2014") vão no campo `legal_basis`, copiadas literalmente da passagem de onde o nugget saiu; não as coloque em `text`. Use lista vazia quando não houver citação.

**R7 — Saída.** Responda somente com o JSON no formato descrito abaixo.

**R8 — Âncora temporal.** Todo nugget que afirma um valor, alíquota, limite ou prazo deve dizer a que período se aplica (ex.: "no ano-calendário de 2023", "na Declaração de Ajuste Anual do exercício de 2024", ou o período que a resposta indicar). Se a resposta não indica o período, use o da pergunta; se nenhuma das duas indica, use o do documento (exercício de 2024, ano-calendário de 2023). Nunca use um ano que você conheça de outra fonte.

**R9 — Não atualizar.** Não "corrija" nenhum valor, prazo ou regra para a legislação que você conhece, mesmo que a lei tenha mudado depois de 2024. Todo número do nugget deve aparecer na pergunta ou na resposta.

**R10 — Exemplos numéricos.** Números que aparecem somente em um exemplo de cálculo ilustrativo não geram nugget, a menos que o exemplo enuncie uma regra; nesse caso o nugget enuncia a regra.

## Casos recorrentes

- **Remissões a outras perguntas** ("ver pergunta 001", "consulte a resposta à pergunta 150"): a remissão em si não gera nugget. Se a frase também afirma algo, gere o nugget com esse conteúdo, sem mencionar o número da pergunta.
- **Notas "Atenção"**: geram nuggets, normalmente `okay`, salvo se forem indispensáveis para responder corretamente à pergunta.
- **Instruções de preenchimento do programa (PGD) ou de telas/fichas**: categoria `procedimento_pgd`; importância conforme a definição abaixo.
- **Cada linha ou frase factual da resposta** deve ser coberta por ao menos um nugget, exceto remissões e exemplos numéricos (R10).

## Campos de cada nugget

- `text`: a afirmação, em português, em uma ou duas frases.
- `importance`: `vital` se uma resposta correta **a esta pergunta** precisa conter esse fato (sem ele a resposta ficaria errada ou enganosa); `okay` se é útil mas não indispensável.
- `category`: uma de
  - `resposta_direta` — o veredito (Sim/Não ou conclusão de uma linha);
  - `regra` — regra geral, tratamento tributário;
  - `condicao` — condição, exceção, requisito ou hipótese;
  - `valor_prazo` — o núcleo do nugget é um valor, limite, alíquota, data ou prazo;
  - `procedimento_pgd` — instrução de preenchimento do programa, ficha, código ou tela;
  - `definicao` — definição de um termo.
- `legal_basis`: lista de citações literais (R6).
- `source_span`: o trecho **literal** da resposta de onde o nugget foi extraído (uma frase ou um item), copiado sem alterações, sem os números de item ("1 -", "a)") no início. Se o nugget combina dois trechos, use o trecho principal.

Ordene os nuggets na ordem em que os fatos aparecem na resposta.

## Formato de saída

```json
{"nuggets": [{"text": "...", "importance": "vital|okay", "category": "resposta_direta|regra|condicao|valor_prazo|procedimento_pgd|definicao", "legal_basis": ["..."], "source_span": "..."}]}
```

## Exemplo 1 (resposta curta com veredito e remissão)

Resumo: TITULAR OU SÓCIO DE EMPRESA
Pergunta: Contribuinte que é titular ou sócio de empresa está obrigado a apresentar a Declaração de Ajuste Anual do exercício 2024?
Resposta:
<<<
Não, a menos que se enquadre nas hipóteses previstas na resposta à pergunta 001. Não é a condição de
titular ou sócio de empresa, por si só, que obriga à apresentação de Declaração de Ajuste Anual.
>>>

```json
{"nuggets": [
 {"text": "A condição de titular ou sócio de empresa, por si só, não obriga a pessoa física a apresentar a Declaração de Ajuste Anual do exercício de 2024.", "importance": "vital", "category": "resposta_direta", "legal_basis": [], "source_span": "Não é a condição de titular ou sócio de empresa, por si só, que obriga à apresentação de Declaração de Ajuste Anual."},
 {"text": "O titular ou sócio de empresa está obrigado a apresentar a Declaração de Ajuste Anual do exercício de 2024 somente se se enquadrar em alguma das hipóteses gerais de obrigatoriedade de apresentação da declaração.", "importance": "vital", "category": "condicao", "legal_basis": [], "source_span": "Não, a menos que se enquadre nas hipóteses previstas na resposta à pergunta 001."}
]}
```

## Exemplo 2 (enumeração; resposta abreviada aqui)

Resumo: OBRIGATORIEDADE
Pergunta: Quem está obrigado a apresentar a Declaração de Ajuste Anual relativa ao exercício de 2024, ano-calendário de 2023?
Resposta:
<<<
Está obrigada a apresentar a Declaração de Ajuste Anual (DAA) referente ao exercício de 2024, a pessoa
física residente no Brasil que, no ano-calendário de 2023:
1 - recebeu rendimentos tributáveis, sujeitos ao ajuste na declaração, cuja soma foi superior a R$ 30.639,90
(trinta mil, seiscentos e trinta e nove reais e noventa centavos);
[...]
4 - realizou operações de alienação em bolsas de valores, de mercadorias, de futuros e assemelhadas:
a) cuja soma foi superior a R$ 40.000,00 (quarenta mil reais); ou
b) com apuração de ganhos líquidos sujeitas à incidência do imposto;
[...]
8 - optou pela isenção do imposto sobre a renda incidente sobre o ganho de capital auferido na venda de
imóveis residenciais, cujo produto da venda seja destinado à aplicação na aquisição de imóveis residenciais
localizados no País, no prazo de 180 (cento e oitenta) dias contados da celebração do contrato de venda, nos
termos do art. 39 da Lei nº 11.196, de 21 de novembro de 2005;
[...]
Atenção:
Dispensa da apresentação da declaração
a - a pessoa física que se enquadrar em uma ou mais das hipóteses de obrigatoriedade previstas
nos itens 1 a 11 fica dispensada de apresentar a Declaração de Ajuste Anual (DAA), caso conste
como dependente em declaração apresentada por outra pessoa física, na qual tenham sido
informados seus rendimentos, bens e direitos, caso os possua;
>>>

```json
{"nuggets": [
 {"text": "Está obrigada a apresentar a Declaração de Ajuste Anual do exercício de 2024 a pessoa física residente no Brasil que, no ano-calendário de 2023, recebeu rendimentos tributáveis sujeitos ao ajuste na declaração cuja soma foi superior a R$ 30.639,90.", "importance": "vital", "category": "valor_prazo", "legal_basis": [], "source_span": "recebeu rendimentos tributáveis, sujeitos ao ajuste na declaração, cuja soma foi superior a R$ 30.639,90"},
 {"text": "Está obrigada a apresentar a Declaração de Ajuste Anual do exercício de 2024 a pessoa física residente no Brasil que, no ano-calendário de 2023, realizou operações de alienação em bolsas de valores, de mercadorias, de futuros e assemelhadas cuja soma foi superior a R$ 40.000,00.", "importance": "vital", "category": "valor_prazo", "legal_basis": [], "source_span": "cuja soma foi superior a R$ 40.000,00 (quarenta mil reais); ou"},
 {"text": "Está obrigada a apresentar a Declaração de Ajuste Anual do exercício de 2024 a pessoa física residente no Brasil que, no ano-calendário de 2023, realizou operações de alienação em bolsas de valores, de mercadorias, de futuros e assemelhadas com apuração de ganhos líquidos sujeitas à incidência do imposto.", "importance": "vital", "category": "condicao", "legal_basis": [], "source_span": "com apuração de ganhos líquidos sujeitas à incidência do imposto;"},
 {"text": "Está obrigada a apresentar a Declaração de Ajuste Anual do exercício de 2024 a pessoa física residente no Brasil que, no ano-calendário de 2023, optou pela isenção do imposto sobre a renda incidente sobre o ganho de capital auferido na venda de imóveis residenciais cujo produto da venda seja aplicado na aquisição de imóveis residenciais localizados no País no prazo de 180 dias contados da celebração do contrato de venda.", "importance": "vital", "category": "condicao", "legal_basis": ["art. 39 da Lei nº 11.196, de 21 de novembro de 2005"], "source_span": "optou pela isenção do imposto sobre a renda incidente sobre o ganho de capital auferido na venda de imóveis residenciais, cujo produto da venda seja destinado à aplicação na aquisição de imóveis residenciais localizados no País, no prazo de 180 (cento e oitenta) dias contados da celebração do contrato de venda"},
 {"text": "A pessoa física que se enquadrar em uma ou mais hipóteses de obrigatoriedade de apresentação da Declaração de Ajuste Anual do exercício de 2024 fica dispensada de apresentá-la caso conste como dependente em declaração apresentada por outra pessoa física, na qual tenham sido informados seus rendimentos, bens e direitos, caso os possua.", "importance": "okay", "category": "condicao", "legal_basis": [], "source_span": "a pessoa física que se enquadrar em uma ou mais das hipóteses de obrigatoriedade previstas nos itens 1 a 11 fica dispensada de apresentar a Declaração de Ajuste Anual (DAA), caso conste como dependente em declaração apresentada por outra pessoa física, na qual tenham sido informados seus rendimentos, bens e direitos, caso os possua;"}
]}
```

(No exemplo 2 a resposta foi abreviada com "[...]"; na tarefa real, cubra **todos** os itens da resposta.)
