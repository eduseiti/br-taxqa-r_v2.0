"""Pydantic models (single source) and the strict JSON schemas sent to the APIs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Importance = Literal["vital", "okay"]
Category = Literal["resposta_direta", "regra", "condicao", "valor_prazo", "procedimento_pgd", "definicao"]
Label = Literal["support", "partial_support", "not_support", "contradicts"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMNugget(_Strict):
    text: str
    importance: Importance
    category: Category
    legal_basis: list[str]
    source_span: str


class LLMNuggetList(_Strict):
    nuggets: list[LLMNugget]


class Assignment(_Strict):
    nugget: int
    justification: str
    label: Label


class AssignmentList(_Strict):
    assignments: list[Assignment]


class ImportanceLabel(_Strict):
    nugget: int
    justification: str
    importance: Importance


class ImportanceList(_Strict):
    labels: list[ImportanceLabel]


Relation = Literal["same", "a_broader", "b_broader", "overlap", "conflict", "none"]


class Alignment(_Strict):
    a: int
    b: list[int]
    relation: Relation
    note: str


class AlignmentList(_Strict):
    alignments: list[Alignment]


class Reconstruction(_Strict):
    answer: str


class MissingFact(_Strict):
    source_span: str
    problem: Literal["missing", "altered"]
    description: str


class MissingList(_Strict):
    missing: list[MissingFact]


class NuggetAudit(_Strict):
    nugget: int
    c1_faithful: bool
    c2_self_contained: bool
    c3_one_unit: bool
    c4_importance: bool
    problem: str
    fix: str


class Omission(_Strict):
    source_span: str
    fact: str


class Redundant(_Strict):
    a: int
    b: int


class Audit(_Strict):
    nuggets: list[NuggetAudit]
    omissions: list[Omission]
    redundant: list[Redundant]


def strict_schema(model: type[BaseModel]) -> dict:
    """Inline ``$defs``, drop titles, require every property, forbid extras (OpenAI strict mode)."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            out = {k: walk(v) for k, v in node.items() if k != "title"}
            if out.get("type") == "object":
                out["additionalProperties"] = False
                out["required"] = list(out.get("properties", {}))
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(raw)


Cause = Literal["judge_error", "other_provision", "corpus_gap", "pgd_practical", "interpretation",
                "not_in_legislation", "nugget_problem"]


class CauseLabel(_Strict):
    evidence: str
    cause: Cause
    confidence: Literal["high", "medium", "low"]
