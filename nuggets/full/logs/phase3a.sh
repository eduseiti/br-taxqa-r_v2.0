#!/bin/bash
# phase 3, part a: alignment, round trip and Flash self-score on the repaired (rep0) sets
cd "$(dirname "$0")/../../.."
P=.venv/bin/python; N=scripts/nuggets/nuggets.py
O="--out nuggets/full --sample all --budget 40 --workers 8"
PS=gpt-6.1-sol.rep0; GS=gemini-3.1-pro.rep0; QS=qwen3.8-max.rep0
$P $N $O align --pairs $PS:$GS,$PS:$QS,$GS:$QS > nuggets/full/logs/align.log 2>&1 &
$P $N $O roundtrip --set $PS > nuggets/full/logs/roundtrip_rep0.log 2>&1 &
$P $N $O selfscore --judge gemini-3.8-flash --sets $PS,$GS,$QS > nuggets/full/logs/selfscore_flash.log 2>&1 &
wait
echo done
