"""Client-side tokenizers for the length guard (plan §5.5).

Specs (``tokenizer`` in models.yaml):
- ``hf:<repo>@<revision>``  the model's own ``tokenizer.json`` (``tokenizers`` library; special
  tokens added, as the server does — Qwen3 appends ``<|endoftext|>``);
- ``tiktoken:<encoding>``   OpenAI encodings;
- ``chars:<n>``             ``ceil(len/n)``, for tests.
"""

from __future__ import annotations

import math
from typing import Callable

Counter = Callable[[list[str]], list[int]]


def load_counter(spec: str) -> Counter:
    kind, _, arg = spec.partition(":")
    if kind == "hf":
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        repo, _, rev = arg.partition("@")
        tok = Tokenizer.from_file(hf_hub_download(repo, "tokenizer.json", revision=rev or None))
        tok.no_truncation()
        tok.no_padding()

        def count(texts: list[str]) -> list[int]:
            return [len(e.ids) for e in tok.encode_batch(texts, add_special_tokens=True)]
        return count
    if kind == "tiktoken":
        import tiktoken

        enc = tiktoken.get_encoding(arg)
        return lambda texts: [len(x) for x in enc.encode_ordinary_batch(texts)]
    if kind == "chars":
        n = int(arg or 4)
        return lambda texts: [max(1, math.ceil(len(t) / n)) for t in texts]
    raise ValueError(f"unknown tokenizer spec {spec!r} (use hf:, tiktoken: or chars:)")


class LengthError(Exception):
    """Inputs above the model's limit. Never truncated: the run stops (plan §1.4 rule 2)."""

    def __init__(self, offenders: list[tuple[str, int]], limit: int):
        self.offenders, self.limit = offenders, limit
        shown = ", ".join(f"{i} ({n})" for i, n in offenders[:20])
        more = f" and {len(offenders) - 20} more" if len(offenders) > 20 else ""
        super().__init__(f"{len(offenders)} input(s) over {limit} tokens: {shown}{more}")


def guard(ids: list[str], n_tokens: list[int], limit: int) -> None:
    offenders = [(i, n) for i, n in zip(ids, n_tokens) if n > limit]
    if offenders:
        raise LengthError(sorted(offenders, key=lambda x: -x[1]), limit)
