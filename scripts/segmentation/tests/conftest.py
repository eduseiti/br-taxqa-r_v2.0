"""Shared fixtures. Small XML fixtures are copied into tests/fixtures (with the parent documents
their annexes need for metadata); the two large ones (decreto_9580_20181122.anexo1,
decreto_3000_19990326, 4.6 MB together) are read from lexml/articulados to avoid duplicating
them in the repository."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SEG = HERE.parent
sys.path.insert(0, str(SEG))

from common import ART_DIR, NAO_DIR, get_tokenizer, metadata_for, read_rows  # noqa: E402
from run_xsl_segmentation import Job, run_jobs  # noqa: E402

FIX = HERE / "fixtures"
ORIG_XSL = SEG / "GeraCSVporArtigoPorAgrupador.xsl"
NEW_XSL = SEG / "segmenta_estatutario.xsl"


def fixture_path(name: str) -> Path:
    for d in (FIX, ART_DIR, NAO_DIR):
        if (d / name).exists():
            return d / name
    pytest.skip(f"fixture {name} not available")


@pytest.fixture(scope="session")
def tok():
    """Fast tokenizer for structural tests (chars/4)."""
    return get_tokenizer("chars:4")


@pytest.fixture(scope="session")
def xsl_out(tmp_path_factory, tok):
    """Run the amended (and the original) XSL once per file; cached for the session."""
    cache: dict = {}
    base = tmp_path_factory.mktemp("xsl")

    def run(name: str, original: bool = False, caput: str = "nao") -> tuple[Path, list[dict], str]:
        """``caput``: the XSL param caput_em_paragrafo ('nao' = base rows, 'frase' = old X3b)."""
        key = (name, original, caput)
        if key not in cache:
            xml = fixture_path(name)
            meta = metadata_for(xml, tok).text()
            out = base / ("orig" if original else f"new_{caput}") / (name[:-4] + ".csv")
            params = {} if original else {"metadados": meta, "caput_em_paragrafo": caput}
            rec = run_jobs([Job(xml, out, params)],
                           ORIG_XSL if original else NEW_XSL, 1)[0]
            assert rec["status"] == "success", rec["error"]
            cache[key] = (out, read_rows(out), meta)
        return cache[key]

    return run
