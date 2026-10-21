#!/bin/bash
# phase 3 planted-error test (stratified_70) and phase 4 known-answer tests (Flash on all; 3.1 Pro on stratified_70)
cd "$(dirname "$0")/../../.."
P=.venv/bin/python; N=scripts/nuggets/nuggets.py; S=gpt-6.1-sol.rep2
B="--out nuggets/full --budget 75 --workers 8"
(
  $P $N $B --sample stratified_70 plant --set $S
  for a in gemini-3.1-pro qwen3.8-max; do
    $P $N $B --sample stratified_70 audit --set $S.planted --auditor $a > nuggets/full/logs/audit_planted_$a.log 2>&1 &
  done
  wait
) > nuggets/full/logs/planted.log 2>&1 &
(
  $P $N $B --sample all known build --set $S
  $P $N $B --sample all known judge --set $S --judge gemini-3.8-flash > nuggets/full/logs/known_flash.log 2>&1
  $P $N $B --sample stratified_70 known judge --set $S --judge gemini-3.1-pro --name stratified_70 > nuggets/full/logs/known_pro.log 2>&1
) > nuggets/full/logs/known.log 2>&1 &
wait
echo finished
