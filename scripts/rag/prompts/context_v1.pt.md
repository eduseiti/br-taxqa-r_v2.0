<!-- context_v1 (RAG plan §6.2). One block per selected text, in context order; blocks are joined by
one blank line. Placeholders: {n} position of the text in the context (1-based); {fonte} document title,
issuing body when the title lacks it, "Anexo" for annex chunks, the citation path of the chunk and,
for a split article, "(parte p de n)"; {texto} the chunk text (it starts with the
"[ Epígrafe | Ementa ]" prefix of the segmentation). Released versions are never edited: a change is
a new file context_vN.pt.md. -->
[Documento {n}] {fonte}
{texto}
