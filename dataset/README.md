---
license: cc-by-4.0
language:
- pt
task_categories:
- question-answering
- text-retrieval
pretty_name: BR-TaxQA-R v2.0
configs:
- config_name: questions
  default: true
  data_files:
  - split: test
    path: questions.jsonl
- config_name: references
  data_files:
  - split: test
    path: references.jsonl
- config_name: documents
  data_files:
  - split: test
    path: documents.jsonl
---

# BR-TaxQA-R v2.0

Questions, gold answers and legal references of Receita Federal's *Perguntas e Respostas IRPF 2024*
(715 questions), with every reference resolved to a document of the v2.0 legal corpus (the referred
acts fetched as `.docx` and parsed to LexML XML).

Built by `scripts/dataset/build_v2_dataset.py`; `build_report.json` holds the counts, the dropped and
unresolved references and the validation results of the build.

## Configurations

All files are JSON Lines with a fixed schema: every key is present in every row (empty list or
`null` when there is no value), so the HF `json` loader gives lists of structs as lists of structs.

### `questions` — one row per question (715)

| Field | Type | Content |
|---|---|---|
| `question_number` | string | `"001"` … `"715"`, as in the source PDF; the key of the other configs |
| `question_summary` | string | the short heading above the question |
| `question_text` | string | the question |
| `answer` | string | full answer as extracted from the PDF, lines joined with `\n` |
| `answer_cleaned` | string | **gold answer**: `answer` without the reference block and "Consulte a pergunta N" lines |
| `linked_questions` | list[string] | questions the answer refers to |
| `references_text` | list[string] | the raw reference block (grey box) of the answer |
| `embedded_references_text` | list[string] | raw citations found inside the answer text |
| `document_ids` | list[string] | distinct corpus documents cited (resolved references only) |
| `n_unresolved_references` | int | references whose act is not in the corpus |

### `references` — one row per cited act per question (1,919)

| Field | Type | Content |
|---|---|---|
| `reference_id` | string | `<question_number>-<nn>` |
| `question_number` | string | question citing it |
| `origin` | string | `explicit` (reference block) or `embedded` (inside the answer text) |
| `cited_title` | string | the act as cited |
| `document_id` | string \| null | corpus document (`documents.document_id`); `null` when the act is not in the corpus |
| `document_urn` | string \| null | LexML URN of that document (same as `doc_urn` of the chunks) |
| `resolution` | string | `auto_exact`, `auto_undated`, `override` (hand-verified) or `not_in_corpus` |
| `resolution_note` | string \| null | why, for `override` and `not_in_corpus` |
| `citation_text` | list[string] | the source text the provisions were parsed from (pieces of the reference block, or embedded citations) |
| `article_ids` | list[string] | distinct cited articles as LexML ids (ranges expanded; `art12-1` for art. 12-A, `art1u` for artigo único) |
| `provisions` | list[struct] | one row per cited unit: `label` (e.g. "art. 12, § 1º, inciso II"), `article_id`, `fragment_id` (LexML id with the full path, e.g. `art12_par1_inc2`, `art1_cpt_inc10`; `null` when the unit has no id form), `annex`, `lexml_file` (LexML file holding the fragment, main or annex; `null` when not found) |
| `provisions_note` | string \| null | reason, when the provisions come from a hand-verified override |
| `annexes` | list[string] | cited annexes |
| `v1_file` | string | the v1.1 `file` value, for traceability |

### `documents` — one row per corpus document (459)

| Field | Type | Content |
|---|---|---|
| `document_id` | string | file stem in `original/` (e.g. `lei_9250_19951226`) |
| `urn` | string | LexML URN |
| `title` | string \| null | epígrafe from the LexML file |
| `statutory` | bool | `original/articulados` (true) or `original/nao_articulados` (false) |
| `number`, `date` | string \| null | from the file stem (`date` as `YYYY-MM-DD`) |
| `original_file`, `lexml_file` | string | paths in the repository |
| `lexml_annex_files` | list[string] | annex LexML files (separate files in the corpus) |
| `v1_files` | list[string] | v1.1 `file` values resolved to this document |
| `n_questions` | int | questions citing it |

## Usage

```python
from datasets import load_dataset

questions  = load_dataset("path/to/dataset", "questions",  split="test")
references = load_dataset("path/to/dataset", "references", split="test")
documents  = load_dataset("path/to/dataset", "documents",  split="test")
```

The nesting of a citation is kept in `fragment_id`: "art. 1º, inciso X e parágrafo único" gives
`art1_cpt_inc10` and `art1_par1u`, and "art. 12, § 1º, inciso II" gives `art12_par1_inc2`. These are
the ids of the LexML XML, so a corpus unit covers a gold provision when its id equals the
`fragment_id` or is its ancestor (prefix up to a `_`).

Gold citations of one question, at document level:

```python
refs = references.filter(lambda r: r["question_number"] == "001" and r["document_id"] is not None)
```

## Changes from v1.1

- New layout: three flat configurations joined by `question_number` / `document_id`, instead of
  one questions file with nested, irregular reference dicts and a loader script.
- `all_formatted_references` is gone (it was the concatenation of the two reference lists);
  `formatted_references` / `formatted_embedded_references` became `references` rows with `origin`.
- References point at corpus documents and LexML URNs instead of `.txt` file names.
- Provisions are parsed from the citation text of the Q&A document, keeping which inciso belongs
  to which paragraph (v1.1 stored flat paragraph/inciso lists), expanding article ranges that v1.1
  cut short, and dropping articles v1.1 attached to acts cited without any.
- Corrections (details in `build_report.json` and the repository notes):
  - Q277: the "Solução de Consulta Interna Cosit nº 5, de 28 de março de 2006" reference is removed
    (no such act exists).
  - Q150: "Convenção Postal Universal" (and the "Convenção de Berna da UPU" entry) → Decreto nº 9.358/2018;
    "Convenção sobre Privilégios e Imunidades das Nações Unidas" → Decreto nº 27.784/1950.
  - Q141: the Brazil–Germany double-taxation accord → Decreto Legislativo nº 92/1975.
  - Q025, Q081: six "embedded" references that do not occur in the answer text are removed.
  - 42 references are marked `not_in_corpus`: the cited act was never fetched, and the file that
    v1.1 used for it was a different act with the same number.
