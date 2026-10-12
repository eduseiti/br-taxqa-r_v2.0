#!/usr/bin/env python3
"""Build the BR-TaxQA-R v2.0 dataset files (questions, references, documents) as JSON Lines.

Inputs
  --questions  BR-TaxQA-R v1.1 questions JSON (HF ``questions_QA_2024_v1.1.json``)
  --canonical  br-taxqa-document-fetcher ``canonical_referred_documents.json`` (v1.1 file name ->
               act type, number, date)
  original/, lexml/, segmented/chunks_all.csv.gz of this repository
  scripts/dataset/reference_overrides.json   hand-verified resolutions and dropped references
  scripts/dataset/answer_overrides.json      hand-verified fixes to v1.1 answer_cleaned (gold answer)
  scripts/dataset/nonstat_lexml_map.tsv      original/nao_articulados stem -> lexml/nao_articulados file
  scripts/lexml/unmatchable_articles.tsv     cited articles known to have no LexML element (reason)

Outputs (in --out, default ``dataset/``)
  questions.jsonl   one row per question (715)
  references.jsonl  one row per cited document per question, pointing at a v2.0 document
  documents.jsonl   one row per document of the v2.0 corpus (original/ + lexml/)
  build_report.json counts, unresolved references and validation results

Provisions (articles, paragraphs, incisos, alíneas, items) are parsed from the citation text of the
Q&A document (v1.1 ``references`` / ``embedded_references``) by ``citations.py``, which keeps the
nesting as LexML fragment ids (``art1_cpt_inc10``, ``art12_par1_inc2``). The v1.1 structured lists
(``formatted_references``) are used only to know which acts a question cites and how they resolve;
their flat paragraph/inciso lists lost the nesting and are not used. Cases the text cannot express
as written are in the ``citations`` section of reference_overrides.json.

Every v1.1 reference is resolved to a document stem of ``original/`` by, in order:
  1. a hand-verified entry in reference_overrides.json (may say "not in corpus", drop a single
     question's reference, or reassign a single question's reference to another document);
  2. exact match of stem prefix + number + date (from the canonical record);
  3. prefix + number when the canonical record has no date.
A reference that none of these resolves makes the build fail, so no reference is silently lost.
Corrections to the canonical list live in the fetcher (a record's ``correction`` field), whose
reason becomes the ``resolution_note``; a record with ``status`` (``nonexistent_act``,
``not_found``) resolves to no document.

Gold answers: ``answer_cleaned`` is v1.1's, with the edits of answer_overrides.json (text the v1
cleaning lost before a "consulte a pergunta N" pointer or in a parenthetical at a line start), and then
without the lines made only of punctuation that the same cleaning left. An edit whose v1 text changed
(SHA-256) or whose ``find`` does not occur exactly ``count`` times makes the build fail.

Guards (rebuild plan §3.3): the build fails on a dead override (a ``files`` entry for a file name
that is not in the canonical list, or that every citing reference drops) and on a contradiction (``not_in_corpus``
while the canonical record resolves automatically); it warns on a redundant override (same answer as
the automatic resolution) and lists the documents no question cites.
"""

import argparse
import csv
import gzip
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from lxml import etree

from citations import RIR, attribute, chain_units, parse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LEX = "{http://www.lexml.gov.br/1.0}"

# canonical type_slug -> stem prefix used in original/ (subset of the fetcher's ACT_TYPES in use)
PREFIX = {
    "ato_declaratorio_comum_cosar": "ad_cosar", "ato_declaratorio_comum_cosit": "ad_cosit",
    "ato_declaratorio_comum_pgfn": "ad_pgfn", "ato_declaratorio_comum_srf": "ad_srf",
    "ato_declaratorio_executivo_codac": "ade_codac", "ato_declaratorio_executivo_cosit": "ade_cosit",
    "ato_declaratorio_executivo_rfb": "ade_rfb", "ato_declaratorio_executivo_srf": "ade_srf",
    "ato_declaratorio_interpretativo_rfb": "adi_rfb", "ato_declaratorio_interpretativo_srf": "adi_srf",
    "ato_declaratorio_normativo_cosit": "adn_cosit", "ato_declaratorio_normativo_cst": "adn_cst",
    "circular_banco_central": "circ_bc", "decreto": "decreto", "decreto_lei": "decreto_lei",
    "despacho": "desp", "instrucao_normativa_rfb": "in_rfb", "instrucao_normativa_srf": "in_srf",
    "lei": "lei", "lei_complementar": "lei_comp", "medida_provisoria": "mp", "nota_pgfn": "nota_pgfn",
    "parecer_cosit": "par_cosit", "parecer_normativo": "pn_cst", "parecer_normativo_cosit": "pn_cosit",
    "parecer_normativo_cst": "pn_cst", "parecer_pgfn": "par_pgfn",
    "portaria_conjunta": "port_conj_tse_srf", "portaria_mf": "port_mf",
    "resolucao_cgpc": "resol_cgpc", "resolucao_cgsn": "resol_cgsn", "resolucao_tse": "resol_tse",
    "solucao_de_consulta": "sc", "solucao_de_consulta_cosit": "sc_cosit",
    "solucao_de_consulta_interna_cosit": "sci_cosit", "solucao_de_divergencia_cosit": "sd_cosit",
}
MONTHS = {m: i + 1 for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}
STEM_RE = re.compile(r"^(?P<prefix>.+?)_(?P<num>\d+(?:-\d+)?)_(?P<date>\d{8}|nodate)$")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def norm_number(n):
    """'9.250' -> '9250', '0042' -> '42'; keeps Medida Provisória suffixes ('2158-35')."""
    if not n:
        return None
    s = re.sub(r"[.\s]", "", str(n))
    m = re.match(r"^0*(\d+)(-\d+)?$", s)
    return m.group(1) + (m.group(2) or "") if m else s


def norm_date(d):
    """'26 de dezembro de 1995' -> '19951226'."""
    m = re.match(r"(\d{1,2})\D+de\s+(\w+)\s+de\s+(\d{4})", (d or "").replace("1º", "1"))
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return f"{m.group(3)}{MONTHS[m.group(2).lower()]:02d}{int(m.group(1)):02d}"


# ---------------------------------------------------------------- provisions

NUM = r"(\d{1,3}(?:\.\d{3})+|\d+)\s*[º°o]?(?:\s*-\s*([A-Z]))?"


def article_id(num, letter):
    """LexML id of an article: '12-A' -> 'art12-1' (suffix letters are numbered A=1, B=2...)."""
    return "art" + num.replace(".", "") + (f"-{ord(letter) - 64}" if letter else "")


def article_ids(raw):
    """LexML ids of a v1.1 'artigo' string; ranges ('10 a 13') are expanded. [] when unparseable."""
    s = re.sub(r"^\s*arts?\.\s*", "", raw or "", flags=re.I)
    ids = []
    for part in re.split(r"\s+e\s+|,\s*(?=\d)", s):
        m = re.match(rf"^\s*{NUM}(?:\s+a\s+{NUM})?", part)
        if not m:
            continue
        a, la, b, lb = m.groups()
        if b and not la and not lb and 0 < int(b.replace(".", "")) - int(a.replace(".", "")) <= 300:
            ids += [f"art{i}" for i in range(int(a.replace(".", "")), int(b.replace(".", "")) + 1)]
        else:
            ids.append(article_id(a, la))
            if b:
                ids.append(article_id(b, lb))
    return ids


def clean_list(xs):
    return [re.sub(r"^§+\s*", "", str(x)).strip() for x in (xs or []) if str(x).strip()]


def v1_article_ids(entry):
    """Article ids of a v1.1 entry (used only to cross-check the text-derived provisions)."""
    ids = []
    for a in entry.get("artigos") or []:
        a = a if isinstance(a, dict) else {"artigo": str(a)}
        ids += [i for i in article_ids(a.get("artigo")) if i not in ids]
    return ids


def locate(fragment, doc_ids, prefer_annex):
    """LexML file of the document that holds ``fragment``: main file first, or the annex files first
    when the citation is to an annex or to the RIR/2018 (the annex of Decreto nº 9.580). None if absent."""
    main_file, main_ids, annexes = doc_ids
    order = list(annexes.items()) + [(main_file, main_ids)] if prefer_annex else [(main_file, main_ids)] + list(annexes.items())
    return next((f for f, ids in order if fragment in ids), None)


def provisions_from(units, doc_ids, cited_title):
    """Rows of ``provisions``: one per cited unit, with its nested LexML fragment id and the file holding it."""
    out = []
    for u in units:
        frag = u.fragment_id
        found = None
        if frag and doc_ids:
            found = locate(frag, doc_ids, prefer_annex=bool(u.annex) or bool(RIR.search(cited_title or "")))
        out.append({"label": u.label, "article_id": u.article_id, "fragment_id": frag, "annex": u.annex,
                    "lexml_file": found, "matchable": bool(frag and found)})
    return out


# ---------------------------------------------------------------- documents

def xml_info(path):
    """URN, title (epígrafe) and all element ids of a LexML file."""
    tree = etree.parse(str(path), etree.XMLParser(huge_tree=True))
    urn = tree.xpath("/l:LexML/l:Metadado/l:Identificacao/@URN", namespaces={"l": LEX[1:-1]})
    epi = tree.xpath("//l:Epigrafe | //l:Agrupamento[@nome='epigrafe']/l:p[1]", namespaces={"l": LEX[1:-1]})
    title = re.sub(r"\s+", " ", "".join(epi[0].itertext())).strip() if epi else None
    return (urn[0] if urn else None), (title or None), set(tree.xpath("//@id"))


def load_documents():
    nonstat = {r["stem"]: r["lexml_file"] for r in csv.DictReader(open(HERE / "nonstat_lexml_map.tsv"), delimiter="\t")}
    docs, ids = {}, {}
    for statutory, folder in ((True, "articulados"), (False, "nao_articulados")):
        # non-statutory sources may be PDFs (parsed from lexml/nao_articulados/_text/<stem>.txt)
        suffixes = (".docx",) if statutory else (".docx", ".pdf")
        for f in sorted(p for p in (ROOT / "original" / folder).iterdir() if p.suffix in suffixes):
            stem = f.stem
            lexml = ROOT / "lexml" / folder / (f"{stem}.xml" if statutory else nonstat[stem])
            urn, title, xml_ids = xml_info(lexml)
            # annexes are separate files: <stem>.anexoN.xml (statutory), <urn file>!anexoN.xml (non-statutory)
            annexes = lexml.parent.glob(f"{stem}.anexo*.xml" if statutory else f"{lexml.stem}!anexo*.xml")
            annexes = sorted(annexes)
            m = STEM_RE.match(stem)
            docs[stem] = {
                "document_id": stem,
                "urn": urn,
                "title": title,
                "statutory": statutory,
                "number": m["num"] if m else None,
                "date": (f"{m['date'][:4]}-{m['date'][4:6]}-{m['date'][6:]}" if m and m["date"] != "nodate" else None),
                "original_file": str(f.relative_to(ROOT)),
                "lexml_file": str(lexml.relative_to(ROOT)),
                "lexml_annex_files": sorted({str(p.relative_to(ROOT)) for p in annexes}),
            }
            ids[stem] = (docs[stem]["lexml_file"], xml_ids,
                         {str(p.relative_to(ROOT)): xml_info(p)[2] for p in annexes})
    return docs, ids


# ---------------------------------------------------------------- resolution

def resolve_auto(canon_rec, stems):
    """(document_id, resolution, note) from the canonical record alone (no overrides)."""
    note = (canon_rec.get("correction") or {}).get("reason")
    if canon_rec.get("status"):
        return None, canon_rec["status"], note
    pfx, num, date = PREFIX.get(canon_rec["type_slug"]), norm_number(canon_rec["number"]), norm_date(canon_rec["date"])
    parsed = {s: m for s in stems if (m := STEM_RE.match(s))}
    if pfx and num:
        hits = [s for s, m in parsed.items() if m["prefix"] == pfx and norm_number(m["num"]) == num
                and (m["date"] == date if date else True)]
        if len(hits) == 1:
            return hits[0], "auto_exact" if date else "auto_undated", note
    return None, None, None


def resolve(canon_rec, stems, overrides):
    """(document_id, resolution, note) for one v1.1 file name."""
    ov = overrides.get(canon_rec["filename"])
    if ov:
        if ov["document_id"] and ov["document_id"] not in stems:
            sys.exit(f"override points at unknown stem: {ov['document_id']}")
        return ov["document_id"], ("override" if ov["document_id"] else ov.get("status", "not_in_corpus")), ov["reason"]
    return resolve_auto(canon_rec, stems)


def check_overrides(canon, overrides, docs, drops, questions):
    """Build guards on ``files`` overrides (rebuild plan §3.3). Returns warnings; exits on errors."""
    cited = defaultdict(set)  # v1.1 file name -> questions citing it
    for q in questions:
        for field in ("formatted_references", "formatted_embedded_references"):
            for e in q[field] or []:
                if e.get("file"):
                    cited[e["file"]].add(q["question_number"])
    errors, warnings = [], []
    for fname, ov in overrides.items():
        if fname not in canon:
            errors.append(f"dead override (no canonical record): {fname}")
            continue
        qs = cited.get(fname, set())
        if qs and all((q, fname) in drops for q in qs):
            errors.append(f"dead override (every reference using it is dropped): {fname}")
            continue
        if not qs:  # still needed: every canonical file name must resolve
            warnings.append(f"override for a file name no question cites: {fname}")
        auto = resolve_auto(canon[fname], docs)
        if ov["document_id"] is None and auto[1] in ("auto_exact", "auto_undated"):
            errors.append(f"contradiction: override says {ov.get('status', 'not_in_corpus')} but the canonical "
                          f"record resolves to {auto[0]}: {fname}")
        elif ov["document_id"] is not None and auto[0] == ov["document_id"]:
            warnings.append(f"redundant override (the canonical record resolves to the same document): {fname}")
    if errors:
        sys.exit("reference_overrides.json:\n  " + "\n  ".join(errors))
    return warnings


PUNCT_LINE = re.compile(r"^\s*[.;,:)]+\s*$")


def load_answer_overrides(questions):
    ov = json.load(open(HERE / "answer_overrides.json", encoding="utf-8"))
    qnums = {q["question_number"] for q in questions}
    by_q = {}
    for a in ov["answers"]:
        if a["question_number"] not in qnums:
            sys.exit(f"answer_overrides.json: unknown question {a['question_number']}")
        by_q[a["question_number"]] = a
    return by_q, ov["rules"]


def clean_answer(qn, text, by_q, rules, log):
    """v1.1 answer_cleaned -> v2.0 gold answer (answer_overrides.json). ``log`` collects what changed."""
    a = by_q.get(qn)
    if a:
        got = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if got != a["v1_sha256"]:
            sys.exit(f"answer_overrides.json: v1 answer_cleaned of {qn} changed (sha256 {got[:12]}…)")
        for e in a["edits"]:
            n = text.count(e["find"])
            if n != e.get("count", 1):
                sys.exit(f"answer_overrides.json: {qn}: find occurs {n} times, expected {e.get('count', 1)}: "
                         f"{e['find'][:60]!r}")
            text = text.replace(e["find"], e["replace"])
        log["edited"].append(qn)
    if rules.get("drop_punctuation_only_lines"):
        # a punctuation-only line ends the previous line when that one has no final punctuation
        # ("… se da união resultou filho" + "."); otherwise it is a leftover and is dropped
        kept, n = [], 0
        for x in text.split("\n"):
            if PUNCT_LINE.match(x):
                n += 1
                if kept and kept[-1].strip() and not re.search(r"[.;:!?)]\s*$", kept[-1]):
                    kept[-1] = kept[-1].rstrip() + x.strip()
                continue
            kept.append(x)
        if n:
            log["punctuation_lines_dropped"][qn] = n
            text = "\n".join(kept)
    return text


def load_unmatchable():
    """(document_id, article_id) -> reason, from scripts/lexml/unmatchable_articles.tsv."""
    path = ROOT / "scripts" / "lexml" / "unmatchable_articles.tsv"
    out = {}
    if path.exists():
        for row in csv.DictReader((ln for ln in open(path, encoding="utf-8") if not ln.startswith("#")),
                                  delimiter="\t"):
            out[(row["document_id"], row["article_id"])] = row["reason"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", default=str(ROOT.parent / "questions_QA_2024_v1.1_manual_fix.json"))
    ap.add_argument("--canonical", default=str(ROOT.parent / "br-taxqa-document-fetcher/output_canonical/canonical_referred_documents.json"))
    ap.add_argument("--chunks", default=str(ROOT / "segmented/chunks_all.csv.gz"))
    ap.add_argument("--out", default=str(ROOT / "dataset"))
    args = ap.parse_args()

    questions = json.load(open(args.questions, encoding="utf-8"))
    canon = {c["filename"]: c for c in json.load(open(args.canonical, encoding="utf-8"))}
    unmatchable = load_unmatchable()
    ov_all = json.load(open(HERE / "reference_overrides.json", encoding="utf-8"))
    overrides = ov_all["files"]
    drops = {(d["question_number"], d["file"]): d["reason"] for d in ov_all["drop"]}
    # (question, origin, file) -> citation text replacing the parsed provisions
    cite_ov = {(c["question_number"], c["origin"], c["file"]): c for c in ov_all.get("citations", [])}
    # (question, file, cited title) -> document: v1.1 attached the wrong file to that one citation
    reassign = {(d["question_number"], d["file"], d["cited_title"]): (d["document_id"], d["reason"])
                for d in ov_all.get("reassign", [])}
    answer_ov, answer_rules = load_answer_overrides(questions)
    answer_log = {"edited": [], "punctuation_lines_dropped": {}}
    docs, xml_ids = load_documents()
    for doc_id, _ in reassign.values():
        if doc_id not in docs:
            sys.exit(f"reassign points at unknown stem: {doc_id}")

    override_warnings = check_overrides(canon, overrides, docs, drops, questions)
    for w in override_warnings:
        print("warning:", w, file=sys.stderr)
    resolved = {}
    for fname, rec in canon.items():
        resolved[fname] = resolve(rec, docs, overrides)
    dropped_files = {f for _, f in drops}
    unresolved = [f for f, r in resolved.items() if r[1] is None and f not in dropped_files]
    if unresolved:
        sys.exit("unresolved v1.1 file names (add them to reference_overrides.json):\n  " + "\n  ".join(unresolved))

    q_rows, r_rows, dropped, skipped_empty, orphans, v1_only = [], [], [], [], [], []
    doc_questions, doc_v1files = defaultdict(set), defaultdict(set)
    for q in questions:
        qn = q["question_number"]
        k = 0
        q_docs = set()
        for origin, field, raw in (("explicit", "formatted_references", "references"),
                                   ("embedded", "formatted_embedded_references", "embedded_references")):
            entries = [e for e in q[field] or [] if e.get("file")]
            skipped_empty += [{"question_number": qn, "field": field, "entry": e} for e in q[field] or [] if not e.get("file")]
            atts, orph = attribute([e.get("título") or "" for e in entries], q[raw], continuation=origin == "explicit")
            overridden = {f for (qq, o, f) in cite_ov if qq == qn and o == origin}
            orphans += [{"question_number": qn, "origin": origin, "chain": c.text, "text": re.sub(r"\s+", " ", t)}
                        for t, c in orph if not overridden]
            for e, att in zip(entries, atts):
                fname = e.get("file")
                if (qn, fname) in drops:
                    dropped.append({"question_number": qn, "origin": origin, "cited_title": e.get("título"),
                                    "v1_file": fname, "reason": drops[(qn, fname)]})
                    continue
                doc_id, how, note = resolved[fname]
                if (qn, fname, e.get("título")) in reassign:
                    (doc_id, note), how = reassign[(qn, fname, e.get("título"))], "override"
                ov = cite_ov.get((qn, origin, fname))
                units = parse(ov["citation"]) if ov else [u for ch in att.chains for u in chain_units(ch)]
                provisions = provisions_from(units, xml_ids.get(doc_id), e.get("título"))
                art_ids = list(dict.fromkeys(p["article_id"] for p in provisions if p["article_id"]))
                if doc_id:
                    _, main_ids, annexes = xml_ids[doc_id]
                    all_ids = main_ids.union(*annexes.values())
                    art_unmatchable = [a for a in art_ids if a not in all_ids]
                else:
                    art_unmatchable = []
                k += 1
                missing_v1 = [a for a in v1_article_ids(e) if a not in art_ids]
                if missing_v1:
                    v1_only.append({"reference_id": f"{qn}-{k:02d}", "cited_title": e.get("título"),
                                    "v1_article_ids": missing_v1, "citation_text": att.pieces})
                r_rows.append({
                    "reference_id": f"{qn}-{k:02d}",
                    "question_number": qn,
                    "origin": origin,
                    "cited_title": e.get("título"),
                    "document_id": doc_id,
                    "document_urn": docs[doc_id]["urn"] if doc_id else None,
                    "resolution": how,
                    "resolution_note": note,
                    "citation_text": att.pieces,
                    "article_ids": art_ids,
                    "article_ids_unmatchable": art_unmatchable,
                    "unmatchable_reasons": {a: unmatchable[(doc_id, a)] for a in art_unmatchable
                                            if (doc_id, a) in unmatchable},
                    "provisions": provisions,
                    "provisions_note": ov["reason"] if ov else None,
                    "annexes": list(dict.fromkeys(clean_list(e.get("anexos")) + [p["annex"] for p in provisions if p["annex"] and not p["article_id"]])),
                    "v1_file": fname,
                })
                if doc_id:
                    q_docs.add(doc_id)
                    doc_questions[doc_id].add(qn)
                    doc_v1files[doc_id].add(fname)
        q_rows.append({
            "question_number": qn,
            "question_summary": q["question_summary"],
            "question_text": q["question_text"],
            "answer": "\n".join(q["answer"]),
            "answer_cleaned": clean_answer(qn, "\n".join(q["answer_cleaned"]), answer_ov, answer_rules, answer_log),
            "linked_questions": q["linked_questions"],
            "references_text": q["references"],
            "embedded_references_text": q["embedded_references"],
            "document_ids": sorted(q_docs),
            "n_unresolved_references": sum(1 for r in r_rows if r["question_number"] == qn and r["document_id"] is None),
        })

    d_rows = []
    for stem, d in docs.items():
        d_rows.append({**d, "v1_files": sorted(doc_v1files[stem]), "n_questions": len(doc_questions[stem])})

    # ------------------------------------------------------------ validation
    art_total = art_found = art_in_annex = 0
    art_missing, frag_missing = [], []
    frag_counts = Counter()
    for r in r_rows:
        if not r["document_id"]:
            continue
        main_file, main_ids, annexes = xml_ids[r["document_id"]]
        annex_ids = set().union(*annexes.values()) if annexes else set()
        for aid in r["article_ids"]:
            art_total += 1
            if aid in main_ids:
                art_found += 1
            elif aid in annex_ids:
                art_in_annex += 1
            else:
                art_missing.append((r["reference_id"], r["document_id"], aid))
        for p in r["provisions"]:
            if not p["fragment_id"]:
                frag_counts["without_id"] += 1
            elif p["lexml_file"] is None:
                frag_counts["missing"] += 1
                frag_missing.append({"reference_id": r["reference_id"], "document_id": r["document_id"],
                                     "label": p["label"], "fragment_id": p["fragment_id"]})
            else:
                frag_counts["found_in_main" if p["lexml_file"] == main_file else "found_in_annex"] += 1
    chunk_urns = set()
    with gzip.open(args.chunks, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            chunk_urns.add(row["doc_urn"])
    urn_count = Counter(d["urn"] for d in d_rows)

    def git_state(repo):
        try:
            commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            dirty = bool(subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True).strip())
        except Exception:
            commit, dirty = None, None
        return commit, dirty

    commit, dirty = git_state(ROOT)
    fetcher_commit, fetcher_dirty = git_state(Path(args.canonical).resolve().parents[1])

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "git": {"commit": commit, "dirty": dirty,
                "fetcher_commit": fetcher_commit, "fetcher_dirty": fetcher_dirty},
        "inputs_sha256": {"questions": sha256(args.questions), "canonical": sha256(args.canonical),
                          "reference_overrides": sha256(HERE / "reference_overrides.json"),
                          "answer_overrides": sha256(HERE / "answer_overrides.json"),
                          "citations_py": sha256(HERE / "citations.py"),
                          "nonstat_lexml_map": sha256(HERE / "nonstat_lexml_map.tsv")},
        "override_warnings": override_warnings,
        "answer_overrides": {"edited": answer_log["edited"],
                             "punctuation_lines_dropped": answer_log["punctuation_lines_dropped"]},
        "counts": {
            "questions": len(q_rows),
            "questions_with_references": sum(1 for q in q_rows if any(r["question_number"] == q["question_number"] for r in r_rows)),
            "references": len(r_rows),
            "references_by_origin": Counter(r["origin"] for r in r_rows),
            "references_by_resolution": Counter(r["resolution"] for r in r_rows),
            "documents": len(d_rows),
            "documents_cited": sum(1 for d in d_rows if d["n_questions"]),
            "v1_files_in_canonical": len(canon),
        },
        "dropped_references": dropped,
        "skipped_empty_v1_entries": skipped_empty,
        "unresolved_references": [{k: r[k] for k in ("reference_id", "cited_title", "v1_file", "resolution_note")}
                                  for r in r_rows if r["document_id"] is None],
        "documents_not_cited": sorted(d["document_id"] for d in d_rows if not d["n_questions"]),
        "v1_files_not_cited_by_questions": sorted(set(canon) - {r["v1_file"] for r in r_rows} - {d["v1_file"] for d in dropped}),
        "validation": {
            "article_ids_checked": art_total,
            "article_ids_found_in_main_xml": art_found,
            "article_ids_found_only_in_annex_xml": art_in_annex,
            "article_ids_missing": [{"reference_id": a, "document_id": b, "article_id": c,
                                     "unmatchable_reason": unmatchable.get((b, c))} for a, b, c in art_missing],
            "article_ids_missing_unexplained": sorted({f"{b} {c}" for _, b, c in art_missing if (b, c) not in unmatchable}),
            "provisions_unmatchable": sum(1 for r in r_rows if r["document_id"] for p in r["provisions"] if not p["matchable"]),
            "provisions": dict(frag_counts),
            "fragment_ids_missing": frag_missing,
            "citation_chains_not_attributed": orphans,
            "v1_article_ids_not_in_citation_text": v1_only,
            "documents_without_chunks": sorted(d["document_id"] for d in d_rows if d["urn"] not in chunk_urns),
            "cited_documents_without_chunks": sorted(d["document_id"] for d in d_rows if d["n_questions"] and d["urn"] not in chunk_urns),
            "duplicate_urns": {u: sorted(d["document_id"] for d in d_rows if d["urn"] == u) for u, n in urn_count.items() if n > 1},
        },
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("questions", q_rows), ("references", r_rows), ("documents", d_rows)):
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    json.dump(report, open(out / "build_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c = report["counts"]
    print(f"questions {c['questions']}  references {c['references']} {dict(c['references_by_resolution'])}  "
          f"documents {c['documents']} (cited {c['documents_cited']})  dropped {len(dropped)}  "
          f"articles found {art_found}+{art_in_annex} (annex)/{art_total}  provisions {dict(frag_counts)}")
    if report["documents_not_cited"]:
        print(f"warning: {len(report['documents_not_cited'])} documents no question cites "
              "(build_report.json -> documents_not_cited)", file=sys.stderr)
    if orphans:
        sys.exit(f"{len(orphans)} citation chains not attributed to any reference (build_report.json -> "
                 "validation.citation_chains_not_attributed); add a 'citations' override")


if __name__ == "__main__":
    main()
