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
