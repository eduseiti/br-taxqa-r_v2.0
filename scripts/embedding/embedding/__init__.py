"""Embedding pipeline for BR-TaxQA-R v2.0 (plan: docs/20260925_122058_embedding_implementation_plan.md).

Modules:
- ``config``    model registry (models.yaml), paths, prompt templates;
- ``tokens``    client-side tokenizers for the length guard;
- ``corpus``    corpus / query loaders (de-duplication, chunk map);
- ``providers`` embedding back-ends behind one interface (``tei``, ``fake``);
- ``endpoint``  HF Inference Endpoint management and the replica meter;
- ``store``     resumable shard store and the release-format writers;
- ``runner``    request packing, concurrent embedding, per-batch validation, finalize;
- ``parity``    served-vs-reference check;
- ``manifest``  provenance helpers (git state, checksums);
- ``costs``     cost ledger.
"""

__version__ = "0.1.0"
