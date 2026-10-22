<!-- context_v2 (Phase 2 note §10). As context_v1, without the repeated document identification of the
chunk texts: the "[ Epígrafe | Ementa | Anexo ]" prefix of each chunk is removed from {texto}; the
epígrafe is already in the header, the annex label replaces "Anexo" in the header, and the ementa is
shown once per document, on its first block in the context ({ementa} = "Ementa: …" + newline there,
empty elsewhere). The selection and its token budget are unchanged (they count the full chunk text).
Placeholders: {n} position (1-based); {fonte} title — issuing body — annex label — citation
(parte p de n); {ementa}; {texto} the chunk text without its prefix. Released versions are never
edited: a change is a new file context_vN.pt.md. -->
[Documento {n}] {fonte}
{ementa}{texto}
