"""Input questions and the stratified samples shared with the RAG pilot."""
from __future__ import annotations

import json
import random
from pathlib import Path

import tiktoken

# Questions used as worked examples in prompts/create_v1.pt.md; never sampled.
PROMPT_EXAMPLES = {"001", "003"}
_enc = tiktoken.get_encoding("o200k_base")


def ntok(s: str) -> int:
    return len(_enc.encode(s))


def load_questions(path: Path) -> list[dict]:
    out = []
    for line in Path(path).read_text().splitlines():
        q = json.loads(line)
        out.append({k: q[k] for k in ("question_number", "question_summary", "question_text", "answer_cleaned")})
    for q in out:
        q["qa_tokens"] = ntok(q["question_text"] + "\n" + q["answer_cleaned"])
    return out


def stratified(questions: list[dict], per_stratum: int, seed: int = 13, strata: int = 10) -> list[str]:
    """``per_stratum`` questions from each answer-length decile (o200k tokens of question + answer).

    ``stratified(qs, 3)`` is ``stratified_30``; ``stratified(qs, 1)`` is its first pick per decile
    (``preview_10``), so the preview questions are a subset of the pilot."""
    pool = sorted((q for q in questions if q["question_number"] not in PROMPT_EXAMPLES),
                  key=lambda q: (q["qa_tokens"], q["question_number"]))
    rng = random.Random(seed)
    picks = []
    n = len(pool)
    for s in range(strata):
        bucket = pool[s * n // strata:(s + 1) * n // strata]
        order = rng.sample(range(len(bucket)), len(bucket))
        picks += [bucket[i]["question_number"] for i in order[:per_stratum]]
    return picks


def user_prompt(q: dict) -> str:
    return (f"Resumo: {q['question_summary']}\nPergunta: {q['question_text']}\nResposta:\n<<<\n"
            f"{q['answer_cleaned'].strip()}\n>>>")
