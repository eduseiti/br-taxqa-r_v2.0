# Nuggetization preview v2/v3 — execution log

**Generated:** 2026-10-12 16:03:49 (local time, from `date +%Y%m%d_%H%M%S`). **Updated** the same day
with the v3 run (§7–§11), and on 2026-10-12 16:38:48 with the pointer-rule discussion and
resolution (§13).
**Implements:** `docs/20261012_154616_nuggetization_preview_open_items_resolution.md` (the resolution
note) §5, steps 1–4.
**Status:** **done.** The v2 creation prompt had an unexpected side effect (§3). The run was paused and
reported, and the user chose the "follow the answer's structure" fix (§5, option 1). With it
(`create_v3`) and the judge fix (`assign_v2`), **both acceptance criteria of the resolution note pass**
(§8, §9). After the pointer-rule decision (§13), the prompts for the phase 1 pilot are
**`create_v4`** and **`assign_v2`**.
**Outputs:** `nuggets/preview_v2/` (creation only, the rejected R2 variant) and `nuggets/preview_v3/`
(final; report `nuggets/preview_v3/report.md`). The v1 preview in `nuggets/preview/` is unchanged
and kept as the "before" state.
**Total cost of the whole preview (v1 + v2 + v3): $2.6258** at standard prices, 210 ledgered calls
(§10).

---

## 1. Changes made

| File | Change |
|---|---|
| `scripts/nuggets/prompts/create_v2.pt.md` | Copy of `create_v1` + the R2 sentence of the resolution note §2.3 |
| `scripts/nuggets/prompts/assign_v2.pt.md` | Copy of `assign_v1`. The old period sentence in `support` is removed, and an **implicit-period** paragraph is added: a missing exercício 2024 / ano-calendário 2023 does not lower the label; another period, or another year's value, is `contradicts` (resolution note §1.4) |
| `scripts/nuggets/nuggets.py` | `--prompt` on `create` (default `create_v2`) and `selfscore` (default `assign_v2`); `selfscore` writes a `manifest.json` per judge and set; global `--budget USD`; loads `.env` with `python-dotenv` (the `GEMINI_API_KEY` line now parses, so `set -a; . ./.env` is no longer needed) |
| `scripts/llm_client/client.py` | **Budget cap:** `LLM(..., budget_usd=)`. Before every API call, retries included, it sums the `--out` ledger (`costs.csv`) and raises `BudgetExceeded` once the total reaches the cap. Concurrent workers can overshoot by at most one call each (≈ $0.10 at worst for these call sizes) |
| `scripts/nuggets/nuggetizer/report.py` | Header lists the prompt of every creator and judge. The phase 1–4 total is marked incomplete when some roles were not run |
| `.gitignore` | `nuggets/**/cache/` and `nuggets/**/input/` (resolution note §3.2) |

**Budget cap test (no API call):** a scratch `--out` with a fake ledger of $5.00 and `--budget 1.0`.
`create` raised `BudgetExceeded` before the first call; no cache file was written and the ledger was
unchanged.

The v1 report (`nuggets/preview/report.md`) was regenerated only to add the prompt header (no API
calls; the v1 ledger still has 90 rows). The v1 self-score runs have no manifest. The report shows
them as `assign_v1 (no manifest)`, which is correct: the prompt text is inside each cached request.

## 2. Creation v2 run

```bash
P=.venv/bin/python; N=scripts/nuggets/nuggets.py
$P $N --out nuggets/preview_v2 sample            # same preview_10 and dataset SHA-256 as v1 (checked)
$P $N --out nuggets/preview_v2 --budget 0.90 create --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max
$P $N --out nuggets/preview_v2 validate
$P $N --out nuggets/preview_v2 report
```

30 calls, 0 retries, 0 validator errors.

### 2.1 Nuggets per question, v1 → v2

| Creator | Total | 503 | 023 | 039 | 710 | 259 | 498 | 564 | 244 | 703 | 624 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `gpt-6.1-sol` | 72 → **93** | 2 → 4 | 3 | 2 | 2 | 3 → **7** | 5 → 6 | 4 | 9 | 13 → 15 | 29 → **41** |
| `gemini-3.1-pro` | 50 → 55 | 2 | 3 → 2 | 2 | 2 → 1 | 3 | 2 → 3 | 4 | 5 → 4 | 6 → **11** | 21 → 23 |
| `qwen3.8-max` | 52 → 52 | 3 → 2 | 3 | 2 | 2 | 3 | 3 | 4 | 5 → 6 | 6 | 21 |

Validation v2: GPT 2 warnings (Q710's pointer to pergunta 674, uncovered as intended; Q624 above
40 nuggets). Gemini 13 warnings: 10 `span_fuzzy`, 8 of them on Q703 where it split item 1;
1 backreference; 1 period; 1 uncovered (the Q710 pointer). Qwen 4 warnings, the same as v1.

## 3. Unexpected result: the R2 sentence makes GPT over-split illustrative lists

The resolution note expected Gemini and Qwen to move toward GPT's granularity (§2.3 acceptance check).
Instead:

- **Qwen did not change** (52 → 52), and **Gemini changed only on Q703** (6 → 11).
- **GPT split further, into illustrative lists.** In Q259 ("criação e venda de cães, passarinhos,
  gatos etc."), the animals are **examples** of one activity. GPT v2 made 3 animals × 2 cases =
  6 nuggets instead of 2 ("Se a criação e venda de cães for exercida de forma eventual…", "… de
  passarinhos…", "… de gatos…"). A system answer that says "animais" would no longer be fully
  supported. In Q624, inciso III ("veículos, aeronaves, embarcações e demais bens móveis sujeitos a
  registro") became four nuggets. Each rule that refers to inciso III was then repeated four times,
  giving 41 nuggets.
- The gap between families **grew**: GPT/Qwen went from 72/52 (1.38) to 93/52 (1.79).

The R2 sentence ("vários objetos ou casos listados … um nugget por objeto") does not separate
**enumerated cases** of the answer (items 1, 2, a), b), incisos I, II), which may have different
treatment, from **objects listed inside one phrase**, which usually share it. GPT read it literally.

## 4. Costs

All costs at standard (synchronous) prices, from the ledgers.

| Run | Calls | Cost | Ledger |
|---|---:|---:|---|
| Preview v1: creation (30) + self-score (60) | 90 | $1.0100 | `nuggets/preview/costs.csv` |
| Probe calls of 2026-10-12 (parameter checks, not in a ledger) | 7 billed (+ 2 rejected for the key) | < $0.01 (prompts of ≈ 20–70 tokens) | — |
| Budget cap test | 0 | $0 | scratch |
| **Preview v2: creation** | 30 | **$0.6639** | `nuggets/preview_v2/costs.csv` |
| **Total so far** | 120 + 7 probes | **≈ $1.68** | |

Per creator, v1 → v2 (10 calls each): `gpt-6.1-sol` $0.1387 → $0.1578 (+14 %), `gemini-3.1-pro`
$0.3080 → $0.3733 (+21 %), `qwen3.8-max` $0.1287 → $0.1327 (+3 %).

**Note for the cost estimate.** Gemini 3.1 Pro reasoned more under v2: 1,151 → 1,561 tokens per call
on average, with latency 47 → 95 s. Its extrapolated full-set cost moved from $10.60 to **$12.80**
(Batch). That is **outside** the 90 % interval of the v1 run ($9.94–11.03). The bootstrap interval
only captures which 10 questions were sampled. It does not cover prompt changes or run-to-run
variation in reasoning length, which here were larger. Cost estimates for the report should
therefore carry a margin of at least ±25 % per creator, not the bootstrap interval alone. The other
two creators moved within their v1 intervals.

## 5. Decision needed before continuing (as reported at the pause)

**R2 (creation prompt).** Options:

1. **(Recommended) "Follow the answer's structure" (`create_v3`).** Replace the R2 sentence with:
   - one nugget per **enumerated item or sub-item** of the answer (1, 2…, a), b)…, I, II…);
   - objects listed **inside one sentence or item** stay in one nugget, unless the answer gives them
     different treatment;
   - illustrative lists ("etc.", "tais como", "por exemplo") are never split;
   - a short negative example based on the Q259 pattern.

   The rule is objective and tied to the answer's own layout, so the enumeration-count check of the
   validator can enforce it. It matches what Gemini and Qwen already do. It still gives inciso-level
   granularity, because the P&R lays incisos out as items (Q624 I–IV, Q703 I/II). It **partly
   reverses** the resolution note §2.3: Q703 item 1 (five operations with one treatment in one
   sentence) becomes one nugget again. The all-or-nothing effect there is left to `partial_support`
   and the non-strict scores (V, A). Cost: one creation rerun, ≈ $0.70 (cap $0.90).
2. **Revert to `create_v1`.** Accept the style differences between families and rely on many-to-one
   alignment (plan v2 §3.5.2). No cost.

**Judge criterion (resolution note §1.4).** This is independent of R2. The clean test is to rerun
the four judges with `assign_v2` on the **v1 nuggets**: same nuggets, only the judge prompt changes,
so any difference is due to the prompt. 60 calls; v1 self-score cost $0.4332, so expect ≈ $0.45,
with a cap of $0.60. It can run before or after the R2 decision.

## 6. Next steps (as planned at the pause; see §7 for what was done)

1. Judge test on the v1 nuggets with `assign_v2` (§5).
2. R2: `create_v3` + rerun creation + validation, or revert (§5).
3. Self-score of the final v2/v3 nugget sets with `assign_v2`; the report; an update of this note
   with the outcome and costs.
4. Commit the code, the docs and the small outputs (`cache/` and `input/` are ignored).

---

## 7. Decision and order of work (after the pause)

- **R2:** option 1, "follow the answer's structure" (user, 2026-10-12).
- **Order:** the user asked to fix R2 before running any judge. The clean A/B test of the judge prompt
  (four judges with `assign_v2` on the **v1** nuggets, §5) was **dropped**. The acceptance criterion
  of the judge fix is absolute (gold self-score ≥ 98 %), so one judge run on the v3 nuggets checks
  it. That saves ≈ $0.45. The A/B would have been run only if v3 had failed the criterion, to find
  the cause.

## 8. Creation v3

`scripts/nuggets/prompts/create_v3.pt.md` = `create_v1` with the last sentence of R2 (one nugget per
enumerated item) replaced by:

> **Siga a estrutura da resposta:** gere **um nugget por item ou subitem enumerado** da resposta
> (1, 2…; a), b)…; I, II…), repetindo em cada um o contexto necessário. Objetos ou casos listados
> **dentro de uma mesma frase ou de um mesmo item** ficam em **um único nugget**, salvo se a resposta
> lhes der tratamentos diferentes. Listas ilustrativas ("etc.", "tais como", "por exemplo", "como")
> nunca são divididas: "os rendimentos de aluguel de imóveis, como casas, apartamentos e salas
> comerciais, são tributáveis" gera um nugget, e não um por tipo de imóvel.

The example is invented on purpose: Q259, the case that exposed the problem, is in `preview_10`
and `stratified_30`, so using it would leak its answer into the prompt. The `create_v2` sentence is
not in v3. Worked example 2 (abridged Q001) already follows the rule.

```bash
P=.venv/bin/python; N=scripts/nuggets/nuggets.py
$P $N --out nuggets/preview_v3 sample
$P $N --out nuggets/preview_v3 --budget 0.90 create --prompt create_v3 --models gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max
$P $N --out nuggets/preview_v3 validate
```

30 calls, 0 retries, **$0.5839**, 0 validator errors.

| Creator | v1 | v2 | **v3** | Per question, v3 (503 023 039 710 259 498 564 244 703 624) | Vital, v1 → v3 |
|---|---:|---:|---:|---|---|
| `gpt-6.1-sol` | 72 | 93 | **53** | 2 2 2 2 3 5 4 4 6 23 | 58 % → 64 % |
| `gemini-3.1-pro` | 50 | 55 | **47** | 2 2 2 2 2 2 3 3 6 23 | 64 % → 49 % |
| `qwen3.8-max` | 52 | 52 | **48** | 2 2 2 2 3 2 4 4 6 21 | 63 % → 60 % |

**Criterion of the resolution note §2.3: passed.** The three families now agree question by question
within ±2 nuggets: GPT/Qwen is 53/48 (1.10), against 1.38 in v1 and 1.79 in v2.

**Checks on the merge** (no API cost):
- **No facts lost.** In Q244, GPT went from 9 nuggets to 4. The four "SCP is a taxpayer of IRPJ /
  CSLL / PIS / Cofins" nuggets became one sentence-level nugget, as the rule says, and every
  statement of the answer is still covered. No `unit_uncovered` warning for GPT.
- **Side effect: merging changes importance.** The four tax nuggets of Q244 were `okay` in v1; the
  merged one is `vital`. Gemini's vital share fell from 64 % to 49 %. Importance labels are the least
  stable part of the nuggets (plan v2 §3.5.2), and the score variants that ignore importance
  (A, A_strict; plan v2 §5.6) are the control for it.
- **Remaining warnings (v3):** GPT 1 (a backreference resolved inside the nugget). Gemini 4: the
  Q498 omission seen in v1 (the reasoning about the estate), two percentage nuggets without a
  period, one backreference. Qwen 6: four fuzzy spans and the same two percentage nuggets without a
  period.

## 9. Gold self-score v3 with `assign_v2`

Same layout as v1: Flash on the three sets; 3.1 Pro, Qwen3.8-Max and GPT on the GPT set. The cap
was `--budget 1.20` for the whole `preview_v3` ledger.

```bash
$P $N --out nuggets/preview_v3 --budget 1.20 selfscore --prompt assign_v2 --judge gemini-3.8-flash \
      --sets gpt-6.1-sol,gemini-3.1-pro,qwen3.8-max
for j in gemini-3.1-pro qwen3.8-max gpt-6.1-sol; do
  $P $N --out nuggets/preview_v3 --budget 1.20 selfscore --prompt assign_v2 --judge $j --sets gpt-6.1-sol
done
$P $N --out nuggets/preview_v3 report
```

60 calls, 0 retries, **$0.3694**.

| Judge | Nugget set | v1 (`create_v1`, `assign_v1`) | **v3 (`create_v3`, `assign_v2`)** |
|---|---|---:|---:|
| `gemini-3.8-flash` | GPT | 94.4 % | **98.1 %** |
| `gemini-3.8-flash` | Gemini | 100.0 % | **100.0 %** |
| `gemini-3.8-flash` | Qwen | 98.1 % | **97.9 %** |
| `gemini-3.1-pro` | GPT | 94.4 % | **98.1 %** |
| `qwen3.8-max` | GPT | 90.3 % | **100.0 %** |
| `gpt-6.1-sol` | GPT | 86.1 % | **100.0 %** |

**Criterion of the resolution note §1.4: passed.** There is no longer any `partial_support` caused
by the implicit period. GPT's v3 nuggets still carry "exercício de 2024" / "ano-calendário de 2023"
where the answer has none (R8 is unchanged), and the judges now accept them. The year-corruption
test of plan v2 §5.7 remains the check that the judges still catch a *different* year.

**All three remaining non-`support` labels are the same case: Q710_N01**, the nugget made from the
pointer sentence "Quando as operações forem realizadas em bolsa, aplica-se o tratamento tributário
previsto na pergunta 674". In v3, all three families made a near-empty `vital` nugget from it
("operações de ouro em bolsa seguem o tratamento das operações em bolsa"). In v1, GPT made none. The
judges hesitate because the content is in another question. Flash's 97.9 % on the Qwen set is
1 nugget of 48, and that nugget is this one.

This is the **pointer** edge case of plan v2 §2 (50 answers still point to other questions). The
prompt's rule ("a pointer gives no nugget unless the sentence also states something") is ambiguous
when the sentence states only "the treatment of another question applies". **Open for the pilot**,
for the user to decide:
- (a) such a sentence gives **no nugget**, which matches what the validator already accepts as
  uncovered;
- (b) it gives an `okay` nugget, so a system answer that explains the actual bolsa rules is not
  required to say it.

(a) is simpler and consistent with the v1 guideline ("pointers to other questions: no nugget").

## 10. Costs (for the report)

All at standard (synchronous) prices, from the ledgers. No call exceeded a budget cap. There were no
retries in any run.

| Run | Prompts | Calls | Creation | Judges | Total | Ledger |
|---|---|---:|---:|---:|---:|---|
| Preview v1 | `create_v1`, `assign_v1` | 90 | $0.5754 | $0.4332 | **$1.0086** | `nuggets/preview/costs.csv` |
| Preview v2 | `create_v2` | 30 | $0.6639 | — | **$0.6639** | `nuggets/preview_v2/costs.csv` |
| Preview v3 | `create_v3`, `assign_v2` | 90 | $0.5839 | $0.3694 | **$0.9533** | `nuggets/preview_v3/costs.csv` |
| Probe calls (parameter checks, 2026-10-12, not ledgered) | — | 7 | | | < $0.01 | — |
| Budget-cap test (scratch ledger) | — | 0 | | | $0 | — |
| **Total** | | **210 + 7** | **$1.8232** | **$0.8026** | **$2.6258 + < $0.01** | |

(The preview note gave v1 as $1.01; the exact ledger sum is $1.0086.)

Per creator and run (10 calls each):

| Creator | v1 | v2 | v3 |
|---|---:|---:|---:|
| `gpt-6.1-sol` | $0.1387 | $0.1578 | $0.1110 |
| `gemini-3.1-pro` | $0.3080 | $0.3733 | $0.3273 |
| `qwen3.8-max` | $0.1287 | $0.1327 | $0.1455 |

## 11. Updated cost estimate (final prompts, `nuggets/preview_v3/report.md` §5–§6)

| | v3-based | v1-based (preview note) | Plan v2 §6.4 |
|---|---:|---:|---:|
| Creation `gpt-6.1-sol`, Batch | $3.75 | $4.64 | ≈ $9 |
| Creation `gemini-3.1-pro`, Batch | $11.23 | $10.60 | ≈ $12 |
| Creation `qwen3.8-max` | $10.03 | $8.90 | ≈ $11–14 |
| OpenAI subtotal, phases 1–4 | $8.63 | $10.69 | ≈ $17–20 |
| Gemini subtotal, phases 1–4 | $33.64 | $35.70 | ≈ $50–55 |
| Alibaba subtotal, phases 1–4 | $24.65 | $27.37 | ≈ $35–40 |
| HF endpoint (not measured) | $10–25 | $10–25 | ≈ $10–25 |
| **Total, phases 1–4** | **≈ $77–92** | ≈ $84–99 | ≈ $115–140 |
| Scoring per run and set: Flash, Batch | $1.26 | $1.32 | ≈ $3.5 |
| Scoring per run and set: 3.1 Pro, Batch | $4.73 | $5.72 | ≈ $10 |
| Scoring per run and set: Qwen3.8-Max | $5.04 | $6.42 | ≈ $11 |
| Scoring per run and set: `gpt-6.1-sol`, Batch | $1.62 | $1.95 | ≈ $9 |

**Margins to use in the report.** Across the three runs, the same creator's extrapolated full-set
cost moved by up to 21 % (Gemini 3.1 Pro: $10.60 → $12.80 → $11.23, Batch). That is more than the
bootstrap intervals, which only reflect which 10 questions were sampled (§4). Recommended
presentation:
- **phases 1–4: ≈ $77–92, with ±25 % on the measured part** (≈ $67 of it), i.e. **≈ $60–110**;
- **scoring:** the per-run figures above × 1.5 until real system-answer lengths are known (RAG
  Phase 3 pilot).

With Flash as primary judge, a 40-run grid scored with three sets is ≈ 40 × 3 × $1.26 × 1.5 ≈
**$230**. With 3.1 Pro it is ≈ **$850**.

## 12. Next steps (status updated 2026-10-12 16:38)

1. ~~Commit the code, the docs and the small outputs of `nuggets/preview*/`.~~ **Done:** commit
   `381be3c`, pushed by the user.
2. ~~Back up the three `cache/` folders outside git.~~ **Done by the user:** the whole `nuggets/`
   folder was copied to `../nuggets_backup_20261012_132700/` (outside the repo). The private HF
   dataset repo of the resolution note §3.2 is still the target from the pilot on.
3. ~~Decide the pointer rule (§9) and fold it into `create_v4`.~~ **Decided and implemented:** §13.
4. Phase 1 pilot on `stratified_30` with the remaining pilot items of plan v2 §4 (1 vs 2 calls,
   same-model noise, known-answer tests, auditors), with `create_v4`, `assign_v2` and a `--budget`
   cap on every run. `create_v4` has not been run yet (§13.5).

---

## 13. Pointer sentences: discussion and resolution (2026-10-12)

### 13.1 The question

§9 recommended that a sentence that only delegates to another question give **no nugget**. The user
asked: if a system answer also includes, correctly, what the pointed answer says, is it penalized?
Compared with an answer that leaves it out, shouldn't the more complete answer be graded better?

### 13.2 How the scores treat extra correct content

The nugget scores (V_strict, V, A_strict, A; plan v2 §5.3) are **recall** scores: the share of the
gold nuggets that the system answer supports. There is no precision term. Content that matches no
nugget counts neither for nor against the answer.

Take two answers to Q710 (gold: "Quando as operações forem realizadas em bolsa, aplica-se o
tratamento tributário previsto na pergunta 674. Já operações de mútuo e de compra vinculada à
revenda … são equiparadas às operações de renda fixa …"):

- **A:** the gold content, plus a correct explanation of how gold operations in bolsa are taxed (the
  content of Q674);
- **B:** only the gold content.

With no pointer nugget, A and B get the **same score**. A is **not penalized**, and its extra correct
content is **not rewarded**. Extra content can lower a score only when it conflicts with a nugget
(`contradicts`); correct content does not.

### 13.3 Why the v3 pointer nugget is worse than no nugget

In v3 all three families made a `vital` nugget from the pointer sentence ("as operações de compra e
venda de ouro realizadas em bolsa seguem o tratamento aplicável às operações em bolsa"). That
nugget rewards *mentioning the delegation*, not its substance:
- B gets credit only if it repeats the pointer sentence;
- A may or may not get credit, depending on whether the judge accepts the concrete bolsa rules as
  support for an almost empty statement. The judges already hesitated on the gold answer itself
  (§9).

That is noise on a `vital` nugget. Without it, A and B are scored on what the Receita actually wrote.

### 13.4 Should the more complete answer score higher? Options considered

| Option | Effect | Assessment |
|---|---|---|
| **(a) No nugget for a pure delegation sentence** | A = B on the gold content | The gold answer is the reference by definition (v1 §3.4.1), and the Receita chose to delegate |
| (b) Keep an `okay` pointer nugget | Credit for repeating the delegation | Noisy (§13.3), even at `okay` |
| (c) **Expand** the pointer: import the pointed question's nuggets into this question | A > B | It **changes the reference**: Q710's gold becomes Q710 + Q674. If Q674 has ≈ 10 nuggets, they swamp Q710's 2 in the per-question average, unless they are kept out of the denominator as "bonus", which breaks the 0–1 scale and comparability with TREC-style scores. It **disagrees with the retrieval evaluation**: `references.jsonl` for Q710 does not include Q674's provisions, so retrieval and answer scoring would use different notions of what is relevant. **Chains:** the pointed answer may point further. Plan v2 §2 already decided "`linked_questions` are not expanded" |

**Effect on the paper's comparisons.** The same rule applies to every strategy, so it cancels in the
paired tests (S2 − S1, etc.). It biases a comparison only if one strategy systematically brings in
the pointed content and its answers then go uncredited. That would make a difference look
**smaller**, never flip its sign.

**Scale** (all 715 gold answers, counted on 2026-10-12): **57 answers (8 %)** contain a pointer
("pergunta NNN"), in **69 sentences**. Most of those sentences carry content around the pointer
(e.g. "… desde que se enquadre como … (ver pergunta X)"), and that content still gets nuggets.
Only pure delegation sentences like Q710's lose their nugget, so the affected set is a subset of
the 69. 237 questions have non-empty `linked_questions`, which is a broader field than in-text
pointers.

### 13.5 Resolution (user, 2026-10-12)

1. **Main nugget set: option (a)**, implemented in `scripts/nuggets/prompts/create_v4.pt.md`
   (= `create_v3` + a rewritten "Remissões" bullet):
   - a sentence that **only delegates** the treatment to another question gives **no nugget**, even
     when it says to which situation the delegation applies; empty nuggets such as "aplica-se um
     tratamento específico" are named as forbidden;
   - a remission that **limits a verdict or a rule** of the answer itself still gives a **condition**
     nugget, without the question number. This keeps worked example 1 (Q003, "Não, a menos que se
     enquadre nas hipóteses previstas na resposta à pergunta 001") consistent with the rule: a flat
     "Não" would be wrong there, so the exception is real content. In Q710 the remission adds
     nothing to judge;
   - a sentence that also states other content gives the nugget for that content.

   The examples in the new bullet are neutral ("pergunta 300", "essas operações"). The first draft
   quoted Q710's own wording ("pergunta 674", "operações em bolsa"); it was rewritten because Q710 is
   in `preview_10` and `stratified_30` (the same leak avoided for Q259 in §8).
2. **A question-level `has_pointer` flag**, filled by the validator (plan v2 §3.1: flags are not
   produced by the LLM). It is copied to every nugget's `flags` and to the question's entry in
   `validation.json`, so the pointer slice is one filter.
3. **Validator changes** (`scripts/nuggets/nuggetizer/validate.py`):
   - an uncovered answer unit that contains a pointer is reported as **`pointer_uncovered`**
     (expected under `create_v4`). It used to be `unit_uncovered`, or `enum_item_uncovered` (a hard
     error) when the unit was an enumerated item. It stays a warning under its own code, because a
     *mixed* sentence whose content part was missed would also land there and is worth a look;
   - a nugget whose text contains a pointer ("pergunta NNN") gets a **`pointer_in_text`** warning.
4. **Optional, later: an "expanded" secondary score on the pointer slice.** Since all 715 questions
   are nuggetized, the pointed question's nuggets are a lookup, not new creation calls. They can be
   added as `okay` nuggets for a secondary score on the `has_pointer` questions only, leaving the
   main metric unchanged. The extra judge cost is cents per run. It answers the user's question
   empirically: does crediting the pointed content change any conclusion? To be decided when the
   scoring plan (phase 5) is fixed.

**Validator test (no API cost)**, on scratch copies of the committed outputs:
- v3 nuggets: Q710 is the only `has_pointer` question of `preview_10`, flagged in all three sets. No
  `pointer_uncovered`, because the v3 pointer nuggets cover the sentence; that is the behaviour
  `create_v4` removes.
- v1 GPT nuggets (made no pointer nugget): Q710 now gives `pointer_uncovered` ("Quando as operações
  forem realizadas em bolsa, aplica-se o tratamento …") instead of `unit_uncovered`.

The committed `nuggets/preview*/` outputs were **not** revalidated, so they still show the old
codes. Reproducing them requires the validator of commit `381be3c`.

`nuggets.py create` now defaults to `--prompt create_v4`; `selfscore` already defaulted to `assign_v2`.
Before this change, the `create` default was still `create_v2`, the rejected variant.

**Not run yet:** `create_v4` itself (no API call was made for this change). Options: check it on
`preview_10` (≈ $0.60, cap $0.90), or let the first pilot run be its check. The expected outcome on
Q710 is no pointer nugget in any family, one `pointer_uncovered` warning per set, and a gold
self-score of 100 % on Q710.
