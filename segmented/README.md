# Segmentation of the legal documents

The legal documents cited by the IRPF 2024 Q&A were converted to LexML XML (`lexml/`) and then
cut into **chunks**, the units that are embedded and retrieved by the RAG system. This page
explains the segmentation strategies we compare, where the chunks are, and shows real examples.

## Segmentation strategies

Brazilian statutes are hierarchical: an **article** has a **caput** (its opening text) and
optionally **paragraphs** (§); the caput and the paragraphs can contain **incisos** (I, II…),
which contain **alíneas** (a, b…), which contain **items** (1, 2…). Articles are gathered into
**groupings**: parts, books, titles, chapters, sections and subsections.

| Strategy | What is indexed |
|---|---|
| **S1** (baseline) | One chunk per **article**, holding the whole article: caput, paragraphs and everything inside them. |
| **S2** | Everything in S1, **plus** one chunk for each caput, paragraph, inciso, alínea and item. A smaller unit is never alone: its chunk also carries the opening text of each unit above it, up to the article label (siblings are left out). A paragraph chunk carries the article label but **not** the caput. |
| **S3** | Everything in S2, **plus** one chunk per **grouping** (chapter, section, title…), holding all the articles of that grouping. Groupings longer than 8,192 tokens are left out. |
| **S2c** | Same chunks as S2, but every paragraph chunk (and the incisos, alíneas and items inside paragraphs) also carries the article's caput text after the article label. Tests whether a paragraph needs its caput to be understood. |
| **S4** | Same as S3, with the caput added the same way as in S2c. |

All strategies index the **same text**; they differ in the **units** that can be matched and
returned. S1 always returns a whole article; S2–S4 can return just the inciso that answers the
question.

Rules common to every strategy:

- **Metadata in every chunk.** Every chunk, at every level (article, paragraph, inciso, grouping,
  non-statutory section), starts with `[ <document title> | <document summary (ementa)> ]`. Long
  ementas are cut to 128 tokens (ending in `…`); documents without an ementa (e.g. the Constitution)
  get only `[ <document title> ]`.
- **Size cap.** Article chunks and non-statutory chunks are at most 1,024 tokens. Longer articles
  are split along their structure into parts (`parte 1/3`, …), each repeating the article label
  and caput.
- **Non-statutory documents** (pareceres, soluções de consulta, court decisions…) have no
  articles. They are cut into their sections, split by paragraph when longer than 1,024 tokens, and
  their tables become separate chunks. They are **identical in all strategies**, so the comparison is
  only about how statutes are cut.
- **Annexes** of statutes are segmented by their content: annexes with articles exactly like
  statutes; annexes with only loose paragraphs or items use each top-level paragraph/item as if it
  were an article; annexes with only text or tables get the non-statutory treatment.

| | S1 | S2 | S3 | S2c | S4 |
|---|---:|---:|---:|---:|---:|
| Chunks | 21,497 | 73,118 | 77,080 | 73,118 | 77,080 |

## Where the segmentation output is

All in `segmented/`:

| Path | Content |
|---|---|
| `chunks_all.csv.gz` | **All chunks of all strategies, in one table** (104,574 rows). Use this one. |
| `statutory/<document>.csv` | Chunks of each statute and statutory annex. |
| `non_statutory/<document>.csv` | Chunks of each non-statutory document and text-only annex. |
| `groupings_over_limit.csv` | Grouping chunks above 8,192 tokens, left out of S3/S4. |
| `segmentation_report.md` | Validation checks and statistics of the last run. |

Main columns: `Texto` (the chunk text that is embedded), `urn` (LexML URN of the unit, e.g.
`urn:lex:br:federal:lei:1995-12-26;9250!art8_par2`), `Rotulo` (readable label), `chunk_id`,
`n_tokens`, `Tipo` (unit type) and `variante` (`base`, or `caput` for the S2c/S4 version of a
paragraph chunk). A strategy is a filter over this table:

```python
import sys; sys.path.insert(0, "scripts/segmentation")
import pandas as pd, strategies
df = pd.read_csv("segmented/chunks_all.csv.gz", low_memory=False)
s2 = strategies.filter(df, "S2")   # "S1", "S2", "S3", "S2C", "S4"
```

The code is in `scripts/segmentation/` (see its `README.md`); the design decisions are in
`docs/20260923_193852_segmentation_strategies_for_rag_experiments.md` and
`docs/20261005_184116_segmentation_s3_vs_lima_ementa_and_caput_strategy_plan.md`.

## Examples

Five random articles of statutes (that have at least one paragraph and belong to a grouping, so
every strategy shows a difference) and five random non-statutory chunks, from different documents.
Long texts are cut with `…`.

### Statutory documents

#### Statutory example 1: `lei_10973_20041202, Art. 3º`

Source: `lexml/articulados/lei_10973_20041202.xml` · URN `urn:lex:br:federal:lei:2004-12-02;10973!art3`

**S1** — one chunk, the whole article:

*article* — `lei_10973_20041202, Art. 3º`
```text
[ LEI Nº 10.973, DE 2 DE DEZEMBRO DE 2004 | Dispõe sobre incentivos à inovação e à pesquisa
científica e tecnológica no ambiente produtivo e dá outras providências. ] Art. 3º A União, os
Estados, o Distrito Federal, os Municípios e as respectivas agências de fomento poderão estimular e
apoiar a constituição de alianças estratégicas e o desenvolvimento de projetos de cooperação
envolvendo empresas, ICTs e entidades privadas sem fins lucrativos voltados para atividades de
pesquisa e desenvolvimento, que objetivem a geração de produtos, processos e serviços inovadores e a
transferência e a difusão de tecnologia. Parágrafo único. O apoio previsto no caput poderá
contemplar as redes e os projetos internacionais de pesquisa tecnológica, as ações de
empreendedorismo tecnológico e de criação de ambientes de inovação, inclusive incubadoras e parques
tecnológicos, e a formação e a capacitação de recursos humanos qualificados. (Artigo com redação
dada pela Lei nº 13.243, de 11.1.2016)
```

**S2** — the S1 chunk plus 2 sub-unit chunk(s):

*caput* — `lei_10973_20041202, Art. 3º, caput`
```text
[ LEI Nº 10.973, DE 2 DE DEZEMBRO DE 2004 | Dispõe sobre incentivos à inovação e à pesquisa
científica e tecnológica no ambiente produtivo e dá outras providências. ] Art. 3º A União, os
Estados, o Distrito Federal, os Municípios e as respectivas agências de fomento poderão estimular e
apoiar a constituição de alianças estratégicas e o desenvolvimento de projetos de cooperação
envolvendo empresas, ICTs e entidades privadas sem fins lucrativos voltados para atividades de
pesquisa e desenvolvimento, que objetivem a geração de produtos, processos e serviços inovadores e a
transferência e a difusão de tecnologia.
```

*paragraph* — `lei_10973_20041202, Art. 3º, Parágrafo único.`
```text
[ LEI Nº 10.973, DE 2 DE DEZEMBRO DE 2004 | Dispõe sobre incentivos à inovação e à pesquisa
científica e tecnológica no ambiente produtivo e dá outras providências. ] Art. 3º Parágrafo único.
O apoio previsto no caput poderá contemplar as redes e os projetos internacionais de pesquisa
tecnológica, as ações de empreendedorismo tecnológico e de criação de ambientes de inovação,
inclusive incubadoras e parques tecnológicos, e a formação e a capacitação de recursos humanos
qualificados. (Artigo com redação dada pela Lei nº 13.243, de 11.1.2016)
```

**S3** — the S2 chunks plus the grouping chunk(s) that contain the article (cut here; the chunk holds the whole grouping):

*grouping* — `lei_10973_20041202, CAPÍTULO II`
```text
[ LEI Nº 10.973, DE 2 DE DEZEMBRO DE 2004 | Dispõe sobre incentivos à inovação e à pesquisa
científica e tecnológica no ambiente produtivo e dá outras providências. ] CAPÍTULO II DO ESTÍMULO À
CONSTRUÇÃO DE AMBIENTES ESPECIALIZADOS E COOPERATIVOS DE INOVAÇÃO Art. 3º A União, os Estados, o
Distrito Federal, os Municípios e as respectivas agências de fomento poderão estimular e apoiar a
constituição de alianças estratégicas e o desenvolvimento de projetos de cooperação envolvendo
empresas, ICTs e entidades privadas sem fins lucrativos voltados para atividades de pesquisa e
desenvolvimento, que …
```

**S2c / S4** — the S2 / S3 chunks, except that the paragraph chunks (and their incisos, alíneas, items) are replaced by these versions, which also carry the caput:

*paragraph* — `lei_10973_20041202, Art. 3º, Parágrafo único.`
```text
[ LEI Nº 10.973, DE 2 DE DEZEMBRO DE 2004 | Dispõe sobre incentivos à inovação e à pesquisa
científica e tecnológica no ambiente produtivo e dá outras providências. ] Art. 3º A União, os
Estados, o Distrito Federal, os Municípios e as respectivas agências de fomento poderão estimular e
apoiar a constituição de alianças estratégicas e o desenvolvimento de projetos de cooperação
envolvendo empresas, ICTs e entidades privadas sem fins lucrativos voltados para atividades de
pesquisa e desenvolvimento, que objetivem a geração de produtos, processos e serviços inovadores e a
transferência e a difusão de tecnologia. Parágrafo único. O apoio previsto no caput poderá
contemplar as redes e os projetos internacionais de pesquisa tecnológica, as ações de
empreendedorismo tecnológico e de criação de ambientes de inovação, inclusive incubadoras e parques
tecnológicos, e a formação e a capacitação de …
```

#### Statutory example 2: `constituição_1988_19881005, Art. 236.`

Source: `lexml/articulados/constituição_1988_19881005.xml` · URN `urn:lex:br:federal:constituicao:1988-10-05;1988!art236`

**S1** — one chunk, the whole article:

*article* — `constituição_1988_19881005, Art. 236.`
```text
[ Constituição da República Federativa do Brasil ] Art. 236. Os serviços notariais e de registro são
exercidos em caráter privado, por delegação do poder público. § 1º Lei regulará as atividades,
disciplinará a responsabilidade civil e criminal dos notários, dos oficiais de registro e de seus
prepostos, e definirá a fiscalização de seus atos pelo Poder Judiciário. § 2º Lei federal
estabelecerá normas gerais para fixação de emolumentos relativos aos atos praticados pelos serviços
notariais e de registro. § 3º O ingresso na atividade notarial e de registro depende de concurso
público de provas e títulos, não se permitindo que qualquer serventia fique vaga, sem abertura de
concurso de provimento ou de remoção, por mais de seis meses.
```

**S2** — the S1 chunk plus 4 sub-unit chunk(s):

*caput* — `constituição_1988_19881005, Art. 236., caput`
```text
[ Constituição da República Federativa do Brasil ] Art. 236. Os serviços notariais e de registro são
exercidos em caráter privado, por delegação do poder público.
```

*paragraph* — `constituição_1988_19881005, Art. 236., § 1º`
```text
[ Constituição da República Federativa do Brasil ] Art. 236. § 1º Lei regulará as atividades,
disciplinará a responsabilidade civil e criminal dos notários, dos oficiais de registro e de seus
prepostos, e definirá a fiscalização de seus atos pelo Poder Judiciário.
```

*paragraph* — `constituição_1988_19881005, Art. 236., § 2º`
```text
[ Constituição da República Federativa do Brasil ] Art. 236. § 2º Lei federal estabelecerá normas
gerais para fixação de emolumentos relativos aos atos praticados pelos serviços notariais e de
registro.
```

*paragraph* — `constituição_1988_19881005, Art. 236., § 3º`
```text
[ Constituição da República Federativa do Brasil ] Art. 236. § 3º O ingresso na atividade notarial e
de registro depende de concurso público de provas e títulos, não se permitindo que qualquer
serventia fique vaga, sem abertura de concurso de provimento ou de remoção, por mais de seis meses.
```

**S3** — the S2 chunks plus the grouping chunk(s) that contain the article (cut here; the chunk holds the whole grouping):

*grouping* — `constituição_1988_19881005, TÍTULO IX`
```text
[ Constituição da República Federativa do Brasil ] TÍTULO IX Das Disposições Constitucionais Gerais
Art. 233. (Revogado) § 1º (Revogado) § 2º (Revogado) § 3º (Revogado) Art. 234. É vedado à União,
direta ou indiretamente, assumir, em decorrência da criação de Estado, encargos referentes a
despesas com pessoal inativo e com encargos e amortizações da dívida interna ou externa da
administração pública, inclusive da indireta. Art. 235. Nos dez primeiros anos da criação de Estado,
serão observadas as seguintes normas básicas: I – a Assembléia Legislativa será composta de
dezessete Deputados se a …
```

**S2c / S4** — the S2 / S3 chunks, except that the paragraph chunks (and their incisos, alíneas, items) are replaced by these versions, which also carry the caput:

*paragraph* — `constituição_1988_19881005, Art. 236., § 1º`
```text
[ Constituição da República Federativa do Brasil ] Art. 236. Os serviços notariais e de registro são
exercidos em caráter privado, por delegação do poder público. § 1º Lei regulará as atividades,
disciplinará a responsabilidade civil e criminal dos notários, dos oficiais de registro e de seus
prepostos, e definirá a fiscalização de seus atos pelo Poder Judiciário.
```

*paragraph* — `constituição_1988_19881005, Art. 236., § 2º`
```text
[ Constituição da República Federativa do Brasil ] Art. 236. Os serviços notariais e de registro são
exercidos em caráter privado, por delegação do poder público. § 2º Lei federal estabelecerá normas
gerais para fixação de emolumentos relativos aos atos praticados pelos serviços notariais e de
registro.
```

*paragraph* — `constituição_1988_19881005, Art. 236., § 3º`
```text
[ Constituição da República Federativa do Brasil ] Art. 236. Os serviços notariais e de registro são
exercidos em caráter privado, por delegação do poder público. § 3º O ingresso na atividade notarial
e de registro depende de concurso público de provas e títulos, não se permitindo que qualquer
serventia fique vaga, sem abertura de concurso de provimento ou de remoção, por mais de seis meses.
```

#### Statutory example 3: `lei_8313_19911223, Art. 6º`

Source: `lexml/articulados/lei_8313_19911223.xml` · URN `urn:lex:br:federal:lei:1991-12-23;8313!art6`

**S1** — one chunk, the whole article:

*article* — `lei_8313_19911223, Art. 6º`
```text
[ LEI Nº 8.313, DE 23 DE DEZEMBRO DE 1991 | Restabelece princípios da Lei nº 7.505, de 2 de julho de
1986, institui o Programa Nacional de Apoio à Cultura - PRONAC e dá outras Providências. ] Art. 6º O
FNC financiará até oitenta por cento do custo total de cada projeto, mediante comprovação, por parte
do proponente, ainda que pessoa jurídica de direito público, da circunstância de dispor do montante
remanescente ou estar habilitado à obtenção do respectivo financiamento, através de outra fonte
devidamente identificada, exceto quanto aos recursos com destinação especificada na origem. § 1º
(VETADO) § 2º Poderão ser considerados, para efeito de totalização do valor restante, bens e
serviços oferecidos pelo proponente para implementação do projeto, a serem devidamente avaliados
pela SEC/PR.
```

**S2** — the S1 chunk plus 3 sub-unit chunk(s):

*caput* — `lei_8313_19911223, Art. 6º, caput`
```text
[ LEI Nº 8.313, DE 23 DE DEZEMBRO DE 1991 | Restabelece princípios da Lei nº 7.505, de 2 de julho de
1986, institui o Programa Nacional de Apoio à Cultura - PRONAC e dá outras Providências. ] Art. 6º O
FNC financiará até oitenta por cento do custo total de cada projeto, mediante comprovação, por parte
do proponente, ainda que pessoa jurídica de direito público, da circunstância de dispor do montante
remanescente ou estar habilitado à obtenção do respectivo financiamento, através de outra fonte
devidamente identificada, exceto quanto aos recursos com destinação especificada na origem.
```

*paragraph* — `lei_8313_19911223, Art. 6º, § 1º`
```text
[ LEI Nº 8.313, DE 23 DE DEZEMBRO DE 1991 | Restabelece princípios da Lei nº 7.505, de 2 de julho de
1986, institui o Programa Nacional de Apoio à Cultura - PRONAC e dá outras Providências. ] Art. 6º §
1º (VETADO)
```

*paragraph* — `lei_8313_19911223, Art. 6º, § 2º`
```text
[ LEI Nº 8.313, DE 23 DE DEZEMBRO DE 1991 | Restabelece princípios da Lei nº 7.505, de 2 de julho de
1986, institui o Programa Nacional de Apoio à Cultura - PRONAC e dá outras Providências. ] Art. 6º §
2º Poderão ser considerados, para efeito de totalização do valor restante, bens e serviços
oferecidos pelo proponente para implementação do projeto, a serem devidamente avaliados pela SEC/PR.
```

**S3** — the S2 chunks plus the grouping chunk(s) that contain the article (cut here; the chunk holds the whole grouping):

*grouping* — `lei_8313_19911223, CAPÍTULO II`
```text
[ LEI Nº 8.313, DE 23 DE DEZEMBRO DE 1991 | Restabelece princípios da Lei nº 7.505, de 2 de julho de
1986, institui o Programa Nacional de Apoio à Cultura - PRONAC e dá outras Providências. ] CAPÍTULO
II DO FUNDO NACIONAL DA CULTURA - FNC Art. 4º Fica ratificado o Fundo de Promoção Cultural, criado
pela Lei nº 7.505, de 2 de julho de 1986, que passará a denominar-se Fundo Nacional da Cultura -
FNC, com o objetivo de captar e destinar recursos para projetos culturais compatíveis com as
finalidades do PRONAC e de: I – estimular a distribuição regional equitativa dos recursos a serem
aplicados …
```

**S2c / S4** — the S2 / S3 chunks, except that the paragraph chunks (and their incisos, alíneas, items) are replaced by these versions, which also carry the caput:

*paragraph* — `lei_8313_19911223, Art. 6º, § 1º`
```text
[ LEI Nº 8.313, DE 23 DE DEZEMBRO DE 1991 | Restabelece princípios da Lei nº 7.505, de 2 de julho de
1986, institui o Programa Nacional de Apoio à Cultura - PRONAC e dá outras Providências. ] Art. 6º O
FNC financiará até oitenta por cento do custo total de cada projeto, mediante comprovação, por parte
do proponente, ainda que pessoa jurídica de direito público, da circunstância de dispor do montante
remanescente ou estar habilitado à obtenção do respectivo financiamento, através de outra fonte
devidamente identificada, exceto quanto aos recursos com destinação especificada na origem. § 1º
(VETADO)
```

*paragraph* — `lei_8313_19911223, Art. 6º, § 2º`
```text
[ LEI Nº 8.313, DE 23 DE DEZEMBRO DE 1991 | Restabelece princípios da Lei nº 7.505, de 2 de julho de
1986, institui o Programa Nacional de Apoio à Cultura - PRONAC e dá outras Providências. ] Art. 6º O
FNC financiará até oitenta por cento do custo total de cada projeto, mediante comprovação, por parte
do proponente, ainda que pessoa jurídica de direito público, da circunstância de dispor do montante
remanescente ou estar habilitado à obtenção do respectivo financiamento, através de outra fonte
devidamente identificada, exceto quanto aos recursos com destinação especificada na origem. § 2º
Poderão ser considerados, para efeito de totalização do valor restante, bens e serviços oferecidos
pelo proponente para implementação do projeto, a serem devidamente avaliados pela SEC/PR.
```

#### Statutory example 4: `lei_10865_20040430, Art. 3º`

Source: `lexml/articulados/lei_10865_20040430.xml` · URN `urn:lex:br:federal:lei:2004-04-30;10865!art3`

**S1** — one chunk, the whole article:

*article* — `lei_10865_20040430, Art. 3º`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) I – a
entrada de bens estrangeiros no território nacional; ou II – o pagamento, o crédito, a entrega, o
emprego ou a remessa de valores a residentes ou domiciliados no exterior como contraprestação por
serviço prestado. § 1º Para efeito do inciso I do caput deste artigo, consideram-se entrados no
território nacional os bens que constem como tendo sido importados e cujo extravio venha a ser
apurado pela administração aduaneira. § 2º O disposto no § 1º deste artigo não se aplica: I – às
malas e às remessas postais internacionais; e II – à mercadoria importada a granel que, por sua
natureza ou condições de manuseio na descarga, esteja sujeita a quebra ou a decréscimo, desde que o
extravio não seja superior a 1% (um por cento). § 3º Na hipótese de ocorrer quebra ou decréscimo em
percentual superior ao fixado no inciso II do § 2º deste artigo, serão exigidas as contribuições
somente em relação ao que exceder a 1% (um por cento).
```

**S2** — the S1 chunk plus 8 sub-unit chunk(s):

*caput* — `lei_10865_20040430, Art. 3º, caput`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) I – a
entrada de bens estrangeiros no território nacional; ou II – o pagamento, o crédito, a entrega, o
emprego ou a remessa de valores a residentes ou domiciliados no exterior como contraprestação por
serviço prestado.
```

*inciso* — `lei_10865_20040430, Art. 3º, caput, Inciso I`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) I – a
entrada de bens estrangeiros no território nacional; ou
```

*inciso* — `lei_10865_20040430, Art. 3º, caput, Inciso II`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) II – o
pagamento, o crédito, a entrega, o emprego ou a remessa de valores a residentes ou domiciliados no
exterior como contraprestação por serviço prestado.
```

*paragraph* — `lei_10865_20040430, Art. 3º, § 1º`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º § 1º Para efeito do inciso I do caput deste artigo, consideram-se entrados
no território nacional os bens que constem como tendo sido importados e cujo extravio venha a ser
apurado pela administração aduaneira.
```

*paragraph* — `lei_10865_20040430, Art. 3º, § 2º`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º § 2º O disposto no § 1º deste artigo não se aplica: I – às malas e às
remessas postais internacionais; e II – à mercadoria importada a granel que, por sua natureza ou
condições de manuseio na descarga, esteja sujeita a quebra ou a decréscimo, desde que o extravio não
seja superior a 1% (um por cento).
```

*inciso* — `lei_10865_20040430, Art. 3º, § 2º, Inciso I`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º § 2º O disposto no § 1º deste artigo não se aplica: I – às malas e às
remessas postais internacionais; e
```

*inciso* — `lei_10865_20040430, Art. 3º, § 2º, Inciso II`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º § 2º O disposto no § 1º deste artigo não se aplica: II – à mercadoria
importada a granel que, por sua natureza ou condições de manuseio na descarga, esteja sujeita a
quebra ou a decréscimo, desde que o extravio não seja superior a 1% (um por cento).
```

*paragraph* — `lei_10865_20040430, Art. 3º, § 3º`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º § 3º Na hipótese de ocorrer quebra ou decréscimo em percentual superior ao
fixado no inciso II do § 2º deste artigo, serão exigidas as contribuições somente em relação ao que
exceder a 1% (um por cento).
```

**S3** — the S2 chunks plus the grouping chunk(s) that contain the article (cut here; the chunk holds the whole grouping):

*grouping* — `lei_10865_20040430, CAPÍTULO II`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] CAPÍTULO II DO FATO GERADOR Art. 3º O fato gerador será: (Vide Lei Complementar nº
214, de 16.1.2025) I – a entrada de bens estrangeiros no território nacional; ou II – o pagamento, o
crédito, a entrega, o emprego ou a remessa de valores a residentes ou domiciliados no exterior como
contraprestação por …
```

**S2c / S4** — the S2 / S3 chunks, except that the paragraph chunks (and their incisos, alíneas, items) are replaced by these versions, which also carry the caput:

*paragraph* — `lei_10865_20040430, Art. 3º, § 1º`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) § 1º Para
efeito do inciso I do caput deste artigo, consideram-se entrados no território nacional os bens que
constem como tendo sido importados e cujo extravio venha a ser apurado pela administração aduaneira.
```

*paragraph* — `lei_10865_20040430, Art. 3º, § 2º`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) § 2º O
disposto no § 1º deste artigo não se aplica: I – às malas e às remessas postais internacionais; e II
– à mercadoria importada a granel que, por sua natureza ou condições de manuseio na descarga, esteja
sujeita a quebra ou a decréscimo, desde que o extravio não seja superior a 1% (um por cento).
```

*inciso* — `lei_10865_20040430, Art. 3º, § 2º, Inciso I`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) § 2º O
disposto no § 1º deste artigo não se aplica: I – às malas e às remessas postais internacionais; e
```

*inciso* — `lei_10865_20040430, Art. 3º, § 2º, Inciso II`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) § 2º O
disposto no § 1º deste artigo não se aplica: II – à mercadoria importada a granel que, por sua
natureza ou condições de manuseio na descarga, esteja sujeita a quebra ou a decréscimo, desde que o
extravio não seja superior a 1% (um por cento).
```

*paragraph* — `lei_10865_20040430, Art. 3º, § 3º`
```text
[ LEI Nº 10.865, DE 30 DE ABRIL DE 2004 | Dispõe sobre a Contribuição para os Programas de
Integração Social e de Formação do Patrimônio do Servidor Público e a Contribuição para o
Financiamento da Seguridade Social incidentes sobre a importação de bens e serviços e dá outras
providências. ] Art. 3º O fato gerador será: (Vide Lei Complementar nº 214, de 16.1.2025) § 3º Na
hipótese de ocorrer quebra ou decréscimo em percentual superior ao fixado no inciso II do § 2º deste
artigo, serão exigidas as contribuições somente em relação ao que exceder a 1% (um por cento).
```

#### Statutory example 5: `lei_9718_19981127, Art. 11.`

Source: `lexml/articulados/lei_9718_19981127.xml` · URN `urn:lex:br:federal:lei:1998-11-27;9718!art11`

**S1** — one chunk, the whole article:

*article* — `lei_9718_19981127, Art. 11.`
```text
[ LEI Nº 9.718, DE 27 DE NOVEMBRO DE 1998 | Altera a Legislação Tributária Federal. ] Art. 11. Sem
prejuízo do disposto nos incisos III e IV do art. 7º da Lei nº 9.532, de 1997, a pessoa jurídica
sucessora poderá classificar, no patrimônio líquido, alternativamente ao disposto no § 2º do
mencionado artigo, a conta que registrar o ágio ou deságio nele mencionado. Parágrafo único. O
disposto neste artigo aplica-se aos fatos geradores ocorridos a partir de 1º de janeiro de 1998.
```

**S2** — the S1 chunk plus 2 sub-unit chunk(s):

*caput* — `lei_9718_19981127, Art. 11., caput`
```text
[ LEI Nº 9.718, DE 27 DE NOVEMBRO DE 1998 | Altera a Legislação Tributária Federal. ] Art. 11. Sem
prejuízo do disposto nos incisos III e IV do art. 7º da Lei nº 9.532, de 1997, a pessoa jurídica
sucessora poderá classificar, no patrimônio líquido, alternativamente ao disposto no § 2º do
mencionado artigo, a conta que registrar o ágio ou deságio nele mencionado.
```

*paragraph* — `lei_9718_19981127, Art. 11., Parágrafo único.`
```text
[ LEI Nº 9.718, DE 27 DE NOVEMBRO DE 1998 | Altera a Legislação Tributária Federal. ] Art. 11.
Parágrafo único. O disposto neste artigo aplica-se aos fatos geradores ocorridos a partir de 1º de
janeiro de 1998.
```

**S3** — the S2 chunks plus the grouping chunk(s) that contain the article (cut here; the chunk holds the whole grouping):

*grouping* — `lei_9718_19981127, CAPÍTULO II`
```text
[ LEI Nº 9.718, DE 27 DE NOVEMBRO DE 1998 | Altera a Legislação Tributária Federal. ] CAPÍTULO II DO
IMPOSTO SOBRE A RENDA Art. 9º As variações monetárias dos direitos de crédito e das obrigações do
contribuinte, em função da taxa de câmbio ou de índices ou coeficientes aplicáveis por disposição
legal ou contratual serão consideradas, para efeitos da legislação do imposto de renda, da
contribuição social sobre o lucro líquido, da contribuição PIS/PASEP e da COFINS, como receitas ou
despesas financeiras, conforme o caso. (Vide Lei Complementar nº 214, de 16.1.2025) Art. 10. Os
dispositivos …
```

**S2c / S4** — the S2 / S3 chunks, except that the paragraph chunks (and their incisos, alíneas, items) are replaced by these versions, which also carry the caput:

*paragraph* — `lei_9718_19981127, Art. 11., Parágrafo único.`
```text
[ LEI Nº 9.718, DE 27 DE NOVEMBRO DE 1998 | Altera a Legislação Tributária Federal. ] Art. 11. Sem
prejuízo do disposto nos incisos III e IV do art. 7º da Lei nº 9.532, de 1997, a pessoa jurídica
sucessora poderá classificar, no patrimônio líquido, alternativamente ao disposto no § 2º do
mencionado artigo, a conta que registrar o ágio ou deságio nele mencionado. Parágrafo único. O
disposto neste artigo aplica-se aos fatos geradores ocorridos a partir de 1º de janeiro de 1998.
```

### Non-statutory documents

#### Non-statutory example 1: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2014-06-25_183, Fundamentos, b), c), parte 3/3`

Source: `lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2014-06-25_183.xml` · the same chunk in every strategy

*text section* — `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2014-06-25_183, Fundamentos, b), c), parte 3/3`
```text
[ Solução de Consulta Cosit nº 183, de 25 de junho de 2014 | IMPOSTO SOBRE A RENDA DE PESSOA FÍSICA
- IRPF ] Fundamentos > b) > c) Art. 176. As jazidas, em lavra ou não, e demais recursos minerais e
os potenciais de energia hidráulica constituem propriedade distinta da do solo, para efeito de
exploração ou aproveitamento, e pertencem à União, garantida ao concessionário a propriedade do
produto da lavra. § 1º A pesquisa e a lavra de recursos minerais e o aproveitamento dos potenciais a
que se refere o "caput" deste artigo somente poderão ser efetuados mediante autorização ou concessão
da União, no interesse nacional, por brasileiros ou empresa constituída sob as leis brasileiras e
que tenha sua sede e administração no País, na forma da lei, que estabelecerá as condições
específicas quando essas atividades se desenvolverem em faixa de fronteira ou terras indígenas.
(Redação dada pela Emenda Constitucional nº 6, de 1995) § 2º - É assegurada participação ao
proprietário do solo nos resultados da lavra, na forma e no valor que dispuser a lei. § 3º - A
autorização de pesquisa será sempre por prazo determinado, e as autorizações e concessões previstas
neste artigo não poderão ser …
```

#### Non-statutory example 2: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2014-12-17_361, Fundamentos, IV -, parte 1/2`

Source: `lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2014-12-17_361.xml` · the same chunk in every strategy

*text section* — `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2014-12-17_361, Fundamentos, IV -, parte 1/2`
```text
[ Solução de Consulta Cosit nº 361, de 17 de dezembro de 2014 | IMPOSTO SOBRE A RENDA DE PESSOA
FÍSICA – IRPF EMENTA: DECLARAÇÃO DE AJUSTE ANUAL. CONTRIBUIÇÕES PREVIDENCIÁRIAS. ATIVIDADES
REMUNERADAS. REGIME PRÓPRIO DE PREVIDÊNCIA SOCIAL. REGIME GERAL DE PREVIDÊNCIA SOCIAL. DEDUÇÃO. O
contribuinte, servidor público ocupante de cargo efetivo da União, amparado por Regime Próprio de
Previdência Social, … ] Fundamentos > IV - as contribuições para a Previdência Social da União, dos
Estados, do Distrito Federal e dos Municípios; (...) 13. Por outro lado, conforme sistematizado no
relatório acima, ao descrever a hipótese a que se refere a consulta, a consulente circunscreve os
fatos exclusivamente à dedução das contribuições previdenciárias na sua Declaração de Ajuste Anual
do IRPF, cuja previsão encontra-se em outro dispositivo, especificamente a alínea “d” do inciso II
do art. 8º da Lei nº 9.250, de 1995, a seguir transcrito: Art. 8º A base de cálculo do imposto
devido no ano-calendário será a diferença entre as somas (grifou-se) I - de todos os rendimentos
percebidos durante o ano-calendário, exceto os isentos, os não-tributáveis, os tributáveis
exclusivamente na fonte e os sujeitos …
```

#### Non-statutory example 3: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2021-03-18_19, Fundamentos, parte 1/2`

Source: `lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2021-03-18_19.xml` · the same chunk in every strategy

*text section* — `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2021-03-18_19, Fundamentos, parte 1/2`
```text
[ Solução de Consulta Cosit nº 19, de 18 de março de 2021 | Imposto sobre a Renda de Pessoa Física -
IRPF ] Fundamentos 3. Preliminarmente, convém alertar que o ato administrativo denominado Solução de
Consulta não se presta a verificar a exatidão dos fatos narrados pelo interessado na respectiva
petição de consulta. Ele se limita a apresentar a interpretação que a Secretaria Especial da Receita
Federal do Brasil (RFB) confere aos dispositivos da legislação tributária relacionados a tais fatos,
partindo da premissa de que há conformidade entre eles e os eventos efetivamente ocorridos. 4.
Assim, a Solução de Consulta não convalida quaisquer informações, interpretações ou ações do
consulente; ademais, dela não decorrerão efeitos caso se constate, a qualquer tempo, que os fatos
descritos não correspondem àqueles que serviram de base hipotética à interpretação apresentada. 5. O
art. 20, inciso II, do Regulamento do Imposto sobre a Renda e Proventos de Qualquer Natureza
(RIR/2018), aprovado pelo Decreto nº 9.580, de 22 de novembro de 2018, prevê a isenção do imposto
para servidores de organizações internacionais, nos seguintes termos: Art. 20. Ficam isentos do
imposto sobre a renda os …
```

#### Non-statutory example 4: `urn_lex_br_procuradoria.geral.fazenda.nacional_nota_2012_1114, nota, parte 1/22`

Source: `lexml/nao_articulados/urn_lex_br_procuradoria.geral.fazenda.nacional_nota_2012_1114.xml` · the same chunk in every strategy

*text section* — `urn_lex_br_procuradoria.geral.fazenda.nacional_nota_2012_1114, nota, parte 1/22`
```text
[ NOTA PGFN/CRJ/Nº 1114/2012 | Portaria PGFN Nº 294/2010. Parecer PGFN/CDA Nº 2025/2011.
Jurisprudência pacífica. Processos submetidos à sistemática dos artigos 543-B e 543-C do CPC.
Delimitação da matéria decidida nos julgados. ] ANEXO (Delimitação da matéria decidida – consoante
solicitação da RFB) I – Julgamentos submetidos à sistemática do art. 543-B (repercussão geral) do
Código de Processo Civil desfavoráveis à Fazenda Nacional 1- RE n. 585.235 Relator: Min. Cezar
Peluso Recorrente: UNIÃO Recorrido: IRMAZI – Administração e Participações LTDA. Data de julgamento:
10/09/2008 Resumo: É inconstitucional o alargamento da base de cálculo do PIS e da COFINS, promovido
pelo art. 3º, §1º da Lei n. 9.718/98, eis que tais exações devem incidir, apenas, sobre as receitas
decorrentes da venda de mercadorias e da prestação de serviços (conceito restritivo de receita
bruta), e não sobre a totalidade das receitas auferidas pela pessoa jurídica (conceito ampliativo de
receita bruta). OBSERVAÇÃO: Como visto, o STF entendeu que a COFINS/PIS somente pode incidir sobre
receitas operacionais das empresas (ligadas às suas atividades principais), sendo inconstitucional a
sua incidência sobre as …
```

#### Non-statutory example 5: `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2020-06-22_50, Fundamentos, I -`

Source: `lexml/nao_articulados/urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2020-06-22_50.xml` · the same chunk in every strategy

*text section* — `urn_lex_br_ministerio.fazenda_secretaria.receita.federal_solucao.consulta_2020-06-22_50, Fundamentos, I -`
```text
[ Solução de Consulta Cosit nº 50, de 22 de junho de 2020 | IMPOSTO SOBRE A RENDA DE PESSOA FÍSICA -
IRPF; NORMAS DE ADMINISTRAÇÃO TRIBUTÁRIA ] Fundamentos > I - em desacordo com os artigos 46 e 47;
(...) (grifou-se) 5. A Instrução Normativa RFB nº 1.396, de 16 de setembro de 2013, que regulamenta
os procedimentos da consulta à interpretação da legislação tributária, nos termos de seu artigo 1º,
trata, em seu art. 18, dos casos de ineficácia. Art. 1º Esta Instrução Normativa trata dos processos
administrativos de consulta sobre interpretação da legislação tributária e aduaneira relativa aos
tributos administrados pela Secretaria da Receita Federal do Brasil (RFB) e sobre classificação de
serviços, intangíveis e outras operações que produzam variações no patrimônio. (...) Art. 3º A
consulta deverá ser formulada por escrito, conforme os modelos constantes nos Anexos I a III a esta
Instrução Normativa, dirigida à autoridade competente da Coordenação mencionada no caput do art. 7º
e apresentada na unidade da RFB do domicílio tributário do consulente. (...) § 2º A consulta deverá
atender aos seguintes requisitos: (...)
```

