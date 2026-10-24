---
license: cc-by-4.0
language:
- pt
pretty_name: BR-TaxQA-R v2.0
task_categories:
- question-answering
- text-retrieval
task_ids:
- open-domain-qa
- document-retrieval
size_categories:
- 100K<n<1M
annotations_creators:
- expert-generated
- machine-generated
source_datasets:
- unicamp-dl/BR-TaxQA-R
tags:
- legal
- tax
- brazil
- portuguese
- rag
- lexml
- nuggets
configs:
- config_name: questions
  default: true
  data_files:
  - split: test
    path: dataset/questions.jsonl
- config_name: references
  data_files:
  - split: test
    path: dataset/references.jsonl
- config_name: documents
  data_files:
  - split: test
    path: dataset/documents.jsonl
- config_name: nuggets
  data_files:
  - split: test
    path: nuggets/v0-auto/nuggets.jsonl
- config_name: chunks
  data_files:
  - split: corpus
    path: segmented/chunks_all.jsonl.gz
---

# BR-TaxQA-R v2.0

Questions, gold answers and legal references of Receita Federal's *Perguntas e Respostas IRPF 2024*
(715 questions on the Brazilian personal income tax), with:

- every cited act resolved to a document of a **453-document legal corpus**, fetched from official sources
  and parsed to **LexML XML** (statutes, decrees, normative instructions, *pareceres*, *soluções de consulta*,
  court decisions…);
- the citations parsed down to the cited provision (article, paragraph, inciso, alínea, item), with the LexML
  id of each one;
- the corpus cut into **retrieval chunks** under five segmentation strategies (article chunks and hierarchical
  sub-article chunks);
- **gold nuggets**: 3,175 atomic facts of the gold answers, for nugget-based evaluation of generated answers.

The RAG evaluation run on this release (embeddings, rankings, contexts, generated answers, nugget scores and
raw LLM responses) is in the companion dataset **BR-TaxQA-R-RAG-eval**. The code that built everything is at
<https://github.com/eduseiti/br-taxqa-r_v2.0>.

## Configurations

Every JSON Lines file has a fixed schema: every key is present in every row (empty list or `null` when there
is no value). The configs join on `question_number`, `document_id` / `urn` and `nugget_id`.

```python
from datasets import load_dataset

repo = "unicamp-dl/BR-TaxQA-R"
questions  = load_dataset(repo, "questions",  split="test")    # 715
references = load_dataset(repo, "references", split="test")    # 1,916
documents  = load_dataset(repo, "documents",  split="test")    # 453
nuggets    = load_dataset(repo, "nuggets",    split="test")    # 3,175
chunks     = load_dataset(repo, "chunks",     split="corpus")  # 104,574 (all strategies)
```

### `questions` — one row per question (715)

| Field | Type | Content |
|---|---|---|
| `question_number` | string | `"001"` … `"715"`, as in the source PDF; the key of the other configs |
| `question_summary` | string | the short heading above the question |
| `question_text` | string | the question |
| `answer` | string | full answer as extracted from the PDF, lines joined with `\n` |
| `answer_cleaned` | string | **gold answer**: `answer` without the reference block and "Consulte a pergunta N" pointers |
| `linked_questions` | list[string] | questions the answer refers to |
| `references_text` | list[string] | the raw reference block (grey box) of the answer |
| `embedded_references_text` | list[string] | raw citations found inside the answer text |
| `document_ids` | list[string] | distinct corpus documents cited |
| `n_unresolved_references` | int | references whose act is not in the corpus (0 for every question) |

### `references` — one row per cited act per question (1,916)

| Field | Type | Content |
|---|---|---|
| `reference_id` | string | `<question_number>-<nn>` |
| `question_number` | string | question citing it |
| `origin` | string | `explicit` (reference block) or `embedded` (inside the answer text) |
| `cited_title` | string | the act as cited |
| `document_id` | string | corpus document (`documents.document_id`) |
| `document_urn` | string | LexML URN of that document (same as `doc_urn` of the chunks) |
| `resolution` | string | `auto_exact`, `auto_undated` or `override` (hand-verified) |
| `resolution_note` | string \| null | why, for `override`, and for an automatic resolution whose record was corrected by hand |
| `citation_text` | list[string] | the source text the provisions were parsed from |
| `article_ids` | list[string] | distinct cited articles as LexML ids (ranges expanded; `art12-1` for art. 12-A, `art1u` for artigo único) |
| `article_ids_unmatchable` | list[string] | cited articles with no element in the document's LexML (score them at document level) |
| `unmatchable_reasons` | dict | article id → reason (treaty articles) |
| `provisions` | list[struct] | one row per cited unit: `label` (e.g. "art. 12, § 1º, inciso II"), `article_id`, `fragment_id` (LexML id with the full path, e.g. `art12_par1_inc2`), `annex`, `lexml_file`, `matchable` |
| `provisions_note` | string \| null | reason, when the provisions come from a hand-verified override |
| `annexes` | list[string] | cited annexes |
| `v1_file` | string | the v1.1 `file` value, for traceability |

A corpus unit covers a gold provision when its LexML id equals the `fragment_id` or is its ancestor (prefix up
to a `_`): "art. 1º, inciso X e parágrafo único" gives `art1_cpt_inc10` and `art1_par1u`.

### `documents` — one row per corpus document (453)

| Field | Type | Content |
|---|---|---|
| `document_id` | string | file stem in `original/` (e.g. `lei_9250_19951226`) |
| `urn` | string | LexML URN |
| `title` | string \| null | epígrafe from the LexML file |
| `statutory` | bool | `original/articulados` (true) or `original/nao_articulados` (false) |
| `number`, `date` | string \| null | from the file stem (`date` as `YYYY-MM-DD`) |
| `original_file`, `lexml_file` | string | paths **in this repository** |
| `lexml_annex_files` | list[string] | annex LexML files (separate files) |
| `v1_files` | list[string] | v1.1 `file` values resolved to this document |
| `n_questions` | int | questions citing it |

### `nuggets` — gold nuggets `v0-auto` (3,175)

Atomic, self-contained statements of the gold answers (`answer_cleaned`), one fact each, in Portuguese.

| Field | Type | Content |
|---|---|---|
| `nugget_id` | string | `Q<question>_N<nn>` |
| `question_number`, `ordinal` | string, int | question and position in the answer |
| `text` | string | the nugget |
| `importance` | string | `vital` (2,262; needed for a correct answer) or `okay` (913) |
| `category` | string | `regra`, `condicao`, `resposta_direta`, `procedimento_pgd`, `valor_prazo`, `definicao` |
| `legal_basis` | list[string] | provisions the answer text attaches to this fact |
| `source_span` | string | the span of `answer_cleaned` it comes from; `span_match` says how it was found |
| `values` | list[struct] | amounts, rates, dates and years in the nugget (`raw`, `kind`, `normalized`) |
| `flags` | struct | `has_pointer`, `temporal`, `short_answer`, `procedimento_pgd`, `prompt_example` |
| `issues` | list | mechanical validation issues (none in the frozen set) |
| `audit` | struct | auditor model → failed criteria and the problem found (135 nuggets flagged by one auditor, 1 by both) |
| `stability` | int \| null | in how many of 3 independent creations the nugget appears (3: 2,925; 2: 112; 1: 25; null: repaired) |
| `source_nugget_id` | string | id in the creator run the set was frozen from |

**How they were made.** GPT-6.1 Sol created the nuggets with prompt `create_v4` (3 replicas). Gemini 3.1 Pro
and Qwen3.8-Max audited them, and flagged nuggets were repaired. The set was then frozen, with none dropped.
Before the freeze, the auditors were tested on planted errors: Gemini 3.1 Pro caught 96 % and Qwen3.8-Max
93 %. Judges for scoring answers against nuggets were selected with 3,354 known-answer tests.
The nuggets are **machine-generated and not human-verified**. Answers that only point to another question
("consulte a pergunta N") get no nugget for the pointer (`flags.has_pointer`). The prompts, runs, audits and
tests are in BR-TaxQA-R-RAG-eval (`nuggets/`).

### `chunks` — the segmented corpus (104,574 rows, all strategies)

`segmented/chunks_all.csv.gz` (the file the segmentation code writes; `chunks_all.jsonl.gz` is the same table for the
viewer). Main columns: `chunk_id`, `Texto` (the text that is embedded), `urn` (LexML URN of
the unit, e.g. `urn:lex:br:federal:lei:1995-12-26;9250!art8_par2`), `doc_urn`, `Rotulo` (readable label),
`Tipo` (unit type), `nivel`, `artigo_id`, `agrupadores_*` (groupings), `parte` / `n_partes` (split articles),
`variante` (`base`, or `caput` for the S2c/S4 version of a paragraph chunk), `n_tokens`, `texto_sha256`.

| Strategy | What is indexed | Chunks |
|---|---|---:|
| **S1** | one chunk per article (caput, paragraphs and everything inside) | 21,497 |
| **S2** | S1 plus one chunk per caput, paragraph, inciso, alínea and item, each carrying the opening text of its ancestors up to the article label (a paragraph chunk does not carry the caput) | 73,118 |
| **S3** | S2 plus one chunk per grouping (chapter, section…) up to 8,192 tokens | 77,080 |
| **S2c** | S2 with the caput added to paragraph chunks | 73,118 |
| **S4** | S3 with the caput added to paragraph chunks | 77,080 |

Every chunk starts with `[ <document title> | <ementa> ]`. Article and non-statutory chunks are capped at 1,024
tokens (longer ones are split into parts). Non-statutory documents are cut into sections and are identical in
all strategies. A strategy is a filter over this table (`scripts/segmentation/strategies.py` in the code
repository). `segmented/README.md` explains the strategies with examples, and `segmentation_report.md` holds
the validation checks.

## Corpus files

| Path | Content |
|---|---|
| `original/articulados/<type>_<number>_<YYYYMMDD>.docx` | 209 statutory documents as fetched |
| `original/nao_articulados/*.docx`, `*.pdf` | 244 non-statutory documents (12 born-digital PDFs) |
| `lexml/articulados/<stem>.xml`, `<stem>.anexoN.xml` | LexML of the statutes (root `ProjetoNorma`), one file per annex (root `Anexo`) |
| `lexml/nao_articulados/urn_lex_br_<authority>_<type>_<date>_<number>.xml` | LexML of the non-statutory documents (root `DocumentoGenerico`) |
| `lexml/nao_articulados/_text/` | cleaned text of the PDF sources (the parser input) |
| `lexml/*/PARSER_VERSION` | parser commit and command line |
| `source/P&R IRPF 2024 - v1.0 - 2024.05.03.pdf` | the Receita Federal source of the questions |
| `dataset/build_report.json` | counts, dropped references, overrides and validation of the build |
| `dataset/reference_overrides.json`, `answer_overrides.json` | the hand-verified corrections to v1.1 and their reasons |

Annexes should be segmented **by content** (has `Artigo` / orphan provisions only / plain text and tables), not
by root element.

```python
from huggingface_hub import hf_hub_download
path = hf_hub_download("unicamp-dl/BR-TaxQA-R", "lexml/articulados/lei_9250_19951226.xml", repo_type="dataset")
```

## Changes from v1.1

- New layout: flat configurations joined by `question_number` / `document_id`, instead of one questions file
  with nested reference dicts and a loader script. v1.1 is still available: `revision="v1.1"`.
- References point at corpus documents and LexML URNs instead of `.txt` file names. Provisions are parsed from
  the citation text, keeping which inciso belongs to which paragraph, expanding article ranges, and dropping
  articles v1.1 attached to acts cited without any.
- New: the LexML corpus, the segmented chunks and the gold nuggets.
- **Gold answers.** The v1 cleaning removed text that belongs to the answer (words before a "consulte a
  pergunta N" pointer on the same line, parentheticals at a line start). 25 answers are restored by
  hand-verified edits, and 22 lose lines made only of punctuation. 47 answers differ from v1.1
  (`build_report.json` → `answer_overrides`).
- **Reference corrections:**
  - Q277: a reference to a non-existent act is removed.
  - Q150, Q141: treaty references are mapped to the decrees that enacted them.
  - Q025, Q081: six "embedded" references that are not in the answer text are removed.
  - Q313, Q187: references to acts that do not exist or were not found are removed.
  - Q249: the reference is pointed at the act that was meant.
  - 42 references that v1.1 attached to a different act with the same number now resolve to the right one.

## License

CC BY 4.0. The legal texts are official acts, which are not protected by copyright in Brazil (Lei nº
9.610/1998, art. 8º, IV). The questions and answers come from Receita Federal do Brasil, *Perguntas e Respostas
IRPF 2024*, v1.0 (2024-05-03).

## Versions

- `v2.0` (this release): the dataset above.
- `v1.1`: the original release (tag `v1.1`).
