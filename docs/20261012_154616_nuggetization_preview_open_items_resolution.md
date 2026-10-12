# Nuggetization preview — resolution of the open items

**Generated:** 2026-10-12 15:46:16 (local time, from `date +%Y%m%d_%H%M%S`)
**Context:** `docs/20261012_114025_nuggetization_preview_10_questions.md` (the preview note) §8 listed
four decisions for the user before phase 1. This note records the discussion of each one and the
resolution. Plan: `docs/20261011_224049_gold_answer_nuggetization_plan_v2.md` (plan v2).
**Status:** decided by the user (2026-10-12): **all recommendations accepted**. Implementation and the
preview rerun are pending (§5).

| # | Item | Resolution |
|---|---|---|
| 1 | R8 period anchor vs the judge | **Option A:** judge prompt treats the P&R period as implicit context. Nuggets unchanged |
| 2 | Nugget granularity across families | **Keep the fine grain**, and make it explicit in R2 so all three families split alike |
| 3 | What to commit from `nuggets/` | **Same pattern as `runs/`:** small outputs in git, `cache/` and `input/` ignored, raw cache released on the HF Hub |
| 4 | `GEMINI_API_KEY` line in `.env` | **Fixed by the user.** Checked: `python-dotenv` alone now loads a key Gemini accepts (HTTP 200) |

---

## 1. Rule R8 and the judge

### 1.1 Problem

R8 (plan v2 §3.2) makes every nugget that states an amount, rate or deadline name its period. If
neither the answer nor the question gives one, the nugget uses the P&R's own period (exercício 2024,
ano-calendário 2023). `gpt-6.1-sol` applied this strictly. In Q564, for example, the deadline rules
("2º mês subsequente", "210 dias", "180 dias") became "Na venda de imóveis residenciais **no
ano-calendário de 2023**, …".

The gold answer never mentions 2023. All four judges labelled these nuggets `partial_support`
("não menciona o ano-calendário de 2023"), against the very text they were extracted from. The gold
self-score of the GPT set fell to 86–94 %, below the 98 % automatic gate (plan v2 §3.5.6). All but
one of the non-`support` labels of the preview had this cause.

The nugget is correct; the scoring of it is the problem. Left as is, every system answer that does
not repeat the year would lose credit on these nuggets. Most good answers would, because the gold
answers do not repeat it either. That is noise unrelated to retrieval, and it pushes V_strict down for
all strategies.

### 1.2 Why R8 stays

R8 is what lets a wrong-year answer be detected. An answer that gives the 2025 rate or limit should be
`contradicts`, and that requires the nugget to say which year its value belongs to (temporal
substitution, plan v2 §5.4). This is also how the S2 hypothesis is tested: inciso chunks, which
isolate one period with its year label, should give fewer wrong-year answers than S1 article chunks.

### 1.3 Options considered

| Option | Change | Pros | Cons |
|---|---|---|---|
| **A (chosen)** | One paragraph in the judge prompt: the P&R period is the implicit context of every answer. A *missing* year is not a defect; a *different* year, or another year's value, is `contradicts` | Nuggets unchanged; the temporal check is kept; one prompt edit | The judge might also become lenient on real wrong-year answers. The year- and value-corruption tests (plan v2 §5.7) measure exactly this |
| B | The creator records where each period came from (`period_source: answer \| question \| document`); the judge ignores `document` periods | More explicit | Schema change, a new judge input, and three nugget sets that must fill the field consistently |
| C | A + B | Covers both sides | Only needed if A alone does not bring the gold self-score to ≥ 98 % |

### 1.4 Resolution

**Option A.** `assign_v1.pt.md` becomes `assign_v2.pt.md` with the implicit-period paragraph. The
creation prompt is unchanged on this point.

**Acceptance check:** rerun the four judges on the preview nuggets with `assign_v2` (≈ 40 calls,
≈ $0.30). The GPT-set gold self-score should reach ≈ 99 % with every judge. If it stays below 98 %,
option B is reconsidered (option C). The check that the judge still catches real year changes is the
year-corruption test of plan v2 §5.7. It runs in the pilot, and its sensitivity must stay ≥ 0.90
(plan v2 §3.5.6).

---

## 2. Granularity: GPT splits more than Gemini and Qwen

### 2.1 Observation

In Q703, item 1 of the answer lists five kinds of operation (renda fixa, fundos, bolsa, ouro and
liquidação futura, swap) that all receive "the same rules as residents":

| Creator | Nuggets for item 1 | Nuggets for Q703 |
|---|---|---:|
| `qwen3.8-max` | 1, with the five kinds | 6 |
| `gemini-3.1-pro` | 1, with the five kinds (reworded) | 6 |
| `gpt-6.1-sol` | 6, one per kind, each repeating the rule | 13 |

The same pattern explains Q244 (9 vs 5 and 5) and Q624 (29 vs 21 and 21). In total, GPT made 72
nuggets on the 10 questions, Gemini 50 and Qwen 52.

### 2.2 Why it matters

- **All-or-nothing on composite nuggets.** A system answer that covers renda fixa, fundos and swap
  but omits ouro gets `partial_support` on Qwen's single nugget, which scores 0 under V_strict. On
  GPT's set it gets 5 of 6.
- **The research question needs the fine grain.** The S2 argument is that sub-article chunks
  retrieve the specific inciso. An answer that got inciso I but not inciso II is exactly the case
  composite nuggets hide.
- **Weights within a question.** Scores are averaged per question, so splitting changes weights only
  inside a question. Item 1 of Q703 weighs 6/13 of the question under the GPT set and 1/6 under the
  Gemini set. Neither is "correct", but giving each fact equal weight is easier to defend.
- **Cost is negligible.** Judge output grows with the number of nuggets (≈ 72/50 here), which is cents
  per run.
- **Cross-family agreement is the real risk.** If GPT splits and the other families do not, the
  stability measure of plan v2 §3.5.2 reports low agreement that reflects style, not disagreement
  about facts. With the human audit postponed, that agreement is the main robustness argument (D8).

GPT over-splits slightly at the edge. "Renda fixa" and "fundos de investimento" come from the same
phrase and still became two nuggets. This is defensible, because a system answer can mention one
without the other.

### 2.3 Resolution

**Keep the fine grain**, which is what R2 already intends, and **make it explicit** so all three
families apply it the same way. Sentence added to R2 in the creation prompt (`create_v1.pt.md` →
`create_v2.pt.md`):

> Quando a resposta aplica uma mesma regra a vários objetos ou casos listados (instrumentos, espécies
> de rendimento, hipóteses), gere um nugget por objeto ou caso, repetindo a regra em cada um.

**Acceptance check:** rerun the three creators on the preview (≈ $0.60) and compare the nuggets per
question. Gemini and Qwen should approach GPT's counts on Q244, Q703 and Q624. The cross-family
alignment (plan v2 §3.5.2) must still be **many-to-one**, since some residual difference in
splitting will remain. Finer tuning of the prompt belongs to the phase 1 prompt iterations.

---

## 3. What to commit from `nuggets/`

### 3.1 Sizes

| `nuggets/preview/` | Size | Content |
|---|---:|---|
| `cache/` | 1.9 MB | raw API responses, ≈ 21 KB per call |
| `input/` | 920 KB | copy of `dataset/questions.jsonl`, reproducible |
| `create/` + `selfscore/` | 340 KB | nuggets, validation, labels, per-call logs, manifests |
| `report.md` | 92 KB | |
| `costs.csv`, `sample.json` | 16 KB | |

The cache does not scale in git. Phases 1–4 are ≈ 10–12k calls (≈ 250 MB of raw responses), and
scoring the answer grid adds tens of thousands more. `embeddings/` and `runs/` already follow a rule
for this: provenance and small results in git, bulk on the HF Hub. Plan v2 D10 already releases the
raw responses with the frozen nuggets.

### 3.2 Resolution

The same pattern as `runs/`:

- **Ignored** (`.gitignore`): `nuggets/**/cache/` and `nuggets/**/input/`. The input copy is
  regenerated from `dataset/questions.jsonl`, whose SHA-256 is recorded in `sample.json`.
- **Versioned:** `nuggets.jsonl`, `validation.json`, `assignments.jsonl`, `calls.jsonl`,
  `manifest.json`, `costs.csv`, `sample.json`, `report.md`, plus the code (`scripts/llm_client/`,
  `scripts/nuggets/`) and the docs notes. These are small, they are what gets reviewed, and they show
  prompt changes as diffs.
- **The raw cache is backed up outside git.** It is the only exact record of non-deterministic
  outputs. From the pilot on, it is pushed to a **private HF dataset repo** at the end of each phase,
  and released publicly with `v0-auto` (D10). The preview cache matters less, because its 10
  questions are regenerated in the pilot.
- **The preview is committed** under these rules. The preview note cites it, and it is the "before"
  state for the changes of §1 and §2.

---

## 4. Effect on plan v2

| Plan v2 | Change |
|---|---|
| §3.2 R2 | Explicit one-nugget-per-listed-object sentence (§2.3); prompt `create_v2.pt.md` |
| §3.2 R8 | Unchanged. The document-period fallback stays |
| §5.2 assignment call | Implicit P&R period: a missing year is not penalized, a different year is `contradicts` (§1.4); prompt `assign_v2.pt.md` |
| §3.5.2 alignment | Must be many-to-one (§2.3) |
| §5.7 known-answer tests | The year-corruption sensitivity of the selected judge now also validates the §1.4 judge change |
| §6.3 reproducibility | Raw cache pushed to a private HF dataset repo at each phase end (§3.2) |
| §8.3 Gemini key | `GEMINI_API_KEY` now loads through `python-dotenv`; the `set -a; . ./.env` step is optional |

The cost estimate of the preview note (§6) is unaffected. The finer split raises judge output by
≈ 10–40 % for Gemini and Qwen sets, which is cents per run.

## 5. Next steps

1. Write `assign_v2.pt.md` (§1.4) and `create_v2.pt.md` (§2.3), keeping the v1 files for the record.
2. Add the `.gitignore` rules (§3.2).
3. Rerun the preview: the three creators with `create_v2`, then validation, then the four judges
   with `assign_v2` (≈ $1). Check the two acceptance criteria (§1.4, §2.3), regenerate
   `nuggets/preview/report.md`, and record the outcome in a dated note.
4. Commit the code, the docs and the small preview outputs.
5. Phase 1 pilot on `stratified_30`.
