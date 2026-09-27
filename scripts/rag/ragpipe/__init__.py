"""ragpipe — the RAG pipeline of the BR-TaxQA-R v2.0 segmentation experiment.

Plan: docs/20260927_204356_rag_pipeline_implementation_plan.md. Stages talk only through files:

    R  retrieval      runs/retrieval/<embedding>/<instruction>/<strategy>/rankings.csv.gz
    RE evaluation     runs/retrieval/<embedding>/<instruction>/eval/<eval_id>/…

Phase 1 implements R and RE. Context selection (``context``) is already used by RE for the
token-budget view, so the retrieval numbers describe the contexts the generator will see.
"""

__version__ = "0.1.0"
