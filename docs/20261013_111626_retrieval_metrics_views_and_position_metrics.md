# Retrieval metrics: what "all resolved gold", the three views and the position metrics mean

**Generated:** 2026-10-13 11:16:26 (local time, from `date +%Y%m%d_%H%M%S`).
**Purpose:** a quick reference that explains how the legal-provision retrieval test is scored, from a Q&A
with the user. It decides nothing new. §4 is a proposal, not implemented.
**Sources:**
- `docs/20260927_204356_rag_pipeline_implementation_plan.md` §2.1 (gold, reachability) and §4.3 (views);
- `docs/20261009_121822_nonstat_reparse_decision_and_pipeline_rerun_log.md` §9 (current results, `v2d`);
- `scripts/rag/ragpipe/evaluation.py`, `metrics.py`, `context.py`;
- `runs/retrieval/jua-4b-mixed/irpf/eval/v2d_either_containment_skip/report.md`.

## 1. "All resolved gold"

The phrase, in titles such as "Recall by budget (v2d, all resolved gold)", says which gold items count in the
denominator.

- **Resolved:** gold items come from `dataset/references.jsonl`. A reference counts only if the dataset build
  resolved it to a corpus document, which gives its document, its `article_ids` and its `provisions[]`
  (parsed from the citation text). In the first IR test, 42 references were `not_in_corpus` and were left out.
  Since the 2026-10-08 rebuild, no question has an unresolved reference. Only references dropped on purpose
  are excluded (144-05 was the latest).
- **All, as opposed to reachable only:** each resolved item is tagged as **reachable** (at least one chunk
  of the strategy can match it) or **unreachable** (e.g. a document without chunks, an article id missing
  from the LexML). The plan reports two views:
  - **(a) all resolved gold:** unreachable items stay in the denominator and count as misses. The result is
    shown next to the **oracle** ceiling, the best recall possible given those gaps;
  - **(b) reachable gold only.**
- **All questions:** "all" also means every question with gold, not a subset. §9.1 of the rerun note adds
  rows for subsets: questions whose gold cites a sub-article provision (366), a whole article (430), or a
  non-statutory document (195).

Current gold (`v2d`): 1,724 document items, 1,958 article items, 2,230 provision items. Unreachable: 13 articles
(the treaty articles) and 48 provisions, so the provision oracle is 0.969.

## 2. The three views

The evaluation scores one ranked list of chunks per question and strategy in three ways (plan §4.3,
`evaluation.py:5–13`). Raw rank is not comparable across strategies: an S1 chunk is a whole article, while an
S2 chunk may be one inciso.

| View | What is counted | Cutoffs | Levels | Question it answers |
|---|---|---|---|---|
| **Token budget** (headline) | Chunks in score order after containment de-duplication, taken while they fit in the budget (Qwen3 tokens) | 1k, 2k, 4k, 8k, 16k | document, article, provision | "With the same amount of context, which strategy brings more of the cited provisions?" |
| **Unit projection** ("unit") | The chunk ranking turned into a ranking of distinct **documents** or **articles**: the position where each first appears. A grouping chunk stands for the articles it contains | R@1, 3, 5, 10, 20, 50, 100; **MRR; nDCG@10** | **document, article only** | "How high does the right article or document rank?" It is the view comparable with other retrieval papers |
| **Raw** | Chunks as retrieved, one rank per chunk | k = 1 … 1000 | all | Diagnostic only |

Plus the **oracle**: whether any chunk of the strategy can hit the item at all (the ceiling).

### 2.1 Token budget: membership, not position

Budget recall is a yes/no test per gold item: was it inside the selected context or not? Its position inside
the window does not matter. How the window is filled (`ragpipe/context.py`):
1. Chunks are taken in score order.
2. A chunk already covered by a higher-ranked one is dropped (containment de-duplication, `containment`).
3. A chunk that does not fit is skipped and the next one is tried (overflow `skip`), until the budget is full.

The same selection code will build the generator's context in Phase 2, so the numbers describe exactly what
the LLM will see. Rank matters only for getting into the window. The five budgets give a coarse view of how
early the gold appears (1k vs 16k).

### 2.2 Unit projection: an example

S2 returns these chunks, best first, for a question whose gold is Lei 9.250 art. 8:

| Chunk rank | Chunk | Article | Distinct article rank |
|---:|---|---|---:|
| 1 | Lei 9.250 art. 4, inciso III | art. 4 | **1** |
| 2 | Lei 9.250 art. 4, § 1º | art. 4 | (already counted) |
| 3 | Lei 9.250 art. 8, § 2º | **art. 8** | **2** |
| 4 | Lei 9.250 art. 8, caput | art. 8 | (already counted) |

At chunk level the gold article first appears at rank 3. In the unit projection it is at rank 2, so its
reciprocal rank is 1/2. A rank then means "the n-th distinct article (or document)", whatever the strategy
cuts its chunks into, which makes S1 and S2 comparable at a fixed k.

## 3. Position metrics today

`scripts/rag/ragpipe/metrics.py` has `reciprocal_rank` (MRR) and `ndcg_at` (binary-gain nDCG).
`evaluation.py:280–290` computes **MRR and nDCG@10 only on the unit projection**, so only at the **document
and article levels**. They are reported in §4 of the eval report, with paired tests (§7 of the report, e.g.
S2 − S1 document MRR +0.045 [+0.024, +0.067], p = 0.0001).

**Unit projection, `v2d`, all resolved gold:**

| Level (questions) | Strategy | R@1 | R@10 | R@100 | MRR | nDCG@10 | Oracle R |
|---|---|---:|---:|---:|---:|---:|---:|
| Document (596) | S1 | 0.237 | 0.753 | 0.969 | 0.635 | 0.592 | 1.000 |
| | S2 | 0.263 | 0.780 | 0.970 | 0.681 | 0.630 | 1.000 |
| | S3 | 0.263 | 0.786 | 0.969 | 0.683 | 0.634 | 1.000 |
| | S2c | 0.250 | 0.789 | 0.965 | 0.665 | 0.626 | 1.000 |
| | S4 | 0.251 | 0.790 | 0.965 | 0.668 | 0.628 | 1.000 |
| Article (553) | S1 | 0.158 | 0.510 | 0.764 | 0.473 | 0.403 | 0.989 |
| | S2 | 0.176 | 0.552 | 0.793 | 0.503 | 0.435 | 0.989 |
| | S3 | 0.175 | 0.538 | 0.781 | 0.497 | 0.428 | 0.989 |
| | S2c | 0.163 | 0.547 | 0.788 | 0.496 | 0.432 | 0.989 |
| | S4 | 0.162 | 0.522 | 0.775 | 0.491 | 0.418 | 0.989 |

**No position metric exists:**
- **At the provision level.** A provision can be only partly covered: S1 never returns an inciso on its
  own, only the whole article that contains it. So there is no clean "first position of this provision" to
  project onto. Provision results have only the budget view (recall, with `full` and `partial` variants) and
  the raw view.
- **In the budget view.** A plain rank is not comparable there: ten S2 chunks (≈ 150 tokens each) and ten S1
  articles (≈ 220 tokens, up to 1,024) are very different amounts of context.

## 4. Proposal (not implemented): token-based position metrics

A position metric is worth adding, **measured in tokens rather than ranks**. Then it works at all three
levels, including provision, and stays comparable across strategies with different chunk sizes.

1. **Tokens to the first gold item** (and to the last), per question, in the budget-view context: how much
   context the generator must read before the evidence appears. Report the median, and the share of questions
   whose first gold item lies within 1k/2k/4k tokens.
2. **Token-discounted gain:** an nDCG-like score whose discount depends on the tokens placed before each hit
   instead of its rank. A simpler alternative is the **area under the recall-vs-budget curve** (1k–16k),
   which summarises the whole curve in one number.

**Why it matters most in Phase 2:** where a passage sits in the prompt affects LLMs ("lost in the middle"),
and the context formatting (RAG plan §6.2) is not decided yet. The chunks could be ordered by score or by
document order. A token-position metric would let us check whether answer quality, measured with nuggets,
follows where the evidence sits, and not only whether it is there.

**Cost:** no API calls. The per-item tables already store ranks (`rank_full`, `rank_any`, `unit_pos`), and
token counts are known. It needs a change in `evaluation.py` and a rerun of `evaluate` (≈ 30 s). Status:
**proposed, waiting for the user's go-ahead**; if accepted, add it to the RAG plan as a Phase 2 item.
