#!/bin/bash
# phase 3, part b: the two auditors on the primary set, with omission candidates
cd "$(dirname "$0")/../../.."
P=.venv/bin/python; N=scripts/nuggets/nuggets.py
O="--out nuggets/full --sample all --budget 56 --workers 8"
for a in gemini-3.1-pro qwen3.8-max; do
  $P $N $O audit --set gpt-6.1-sol.rep0 --auditor $a --others gemini-3.1-pro.rep0,qwen3.8-max.rep0 \
     --candidates-from gpt-6.1-sol.rep0 > nuggets/full/logs/audit_$a.log 2>&1 &
done
wait
