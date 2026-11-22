---
title: BR-TaxQA-R explorer
emoji: 📑
colorFrom: green
colorTo: blue
sdk: static
app_file: index.html
pinned: false
license: cc-by-4.0
short_description: Corpus, questions, retrieval and answers of BR-TaxQA-R v2.0
---

# BR-TaxQA-R v2.0: corpus & question explorer

A static, browser-only explorer of the BR-TaxQA-R v2.0 RAG experiments:

- **Questions** (`#/q`): the 715 questions of the IRPF 2024 "Perguntas e Respostas", with the official answer and
  its gold nuggets, the referred legal documents, the gold segments under each segmentation strategy (S1, S2, S3,
  S2c, S4), the retrieval rankings, the generator contexts and prompts, and the scored answers.
- **Corpus** (`#/d`): the 453 legal documents (LexML), with their structure compared across the segmentation
  strategies and the questions that cite each article.

The results dashboard (`dashboard/index.html`) is linked from the explorer's header.

Data: [BR-TaxQA-R](https://huggingface.co/datasets/eduseiti/BR-TaxQA-R) (benchmark and corpus) and
[BR-TaxQA-R-RAG-eval](https://huggingface.co/datasets/eduseiti/BR-TaxQA-R-RAG-eval) (evaluation data). The Space
holds a frozen copy of the explorer's data; `space_manifest.json` records the git commit it was built from.

**Direct links:** on huggingface.co the page runs in an iframe, so the `#/…` address of a question or document is
not shown. Use the direct URL to share one, e.g.
`https://eduseiti-br-taxqa-r-explorer.static.hf.space/#/q/123`.
