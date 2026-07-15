"""
evals/run_eval.py — Held-out accuracy eval for the complexity classifier.

Scores gateway.classifier.classify() against a hand-labeled, held-out query set
(evals/eval_set.jsonl) that shares ZERO utterances with the routes defined in
classifier.py. Reusing route utterances would fake ~100% accuracy; fresh queries
give an honest generalization number — this is the metric quoted in CLAUDE.md.

Run from the repo root:

    python -m evals.run_eval

Prints overall accuracy, a 3x3 confusion matrix, and per-tier precision/recall.
Exits non-zero if accuracy falls below TARGET (0.80, the Week-3 bar) so the eval
can gate CI.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from gateway.classifier import classify, _simple_route, _medium_route, _complex_route

TIERS = ["simple", "medium", "complex"]
TARGET = 0.80
EVAL_PATH = Path(__file__).with_name("eval_set.jsonl")


def load_eval_set() -> list[dict]:
    rows = []
    with EVAL_PATH.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("label") not in TIERS:
                raise ValueError(f"{EVAL_PATH.name}:{lineno} — bad label {row.get('label')!r}")
            rows.append(row)
    return rows


def assert_held_out(rows: list[dict]) -> None:
    """Fail loud if any eval query is verbatim a route utterance — that would
    inflate the score and make the metric dishonest."""
    trained = set()
    for route in (_simple_route, _medium_route, _complex_route):
        trained.update(u.strip().lower() for u in route.utterances)
    leaked = [r["query"] for r in rows if r["query"].strip().lower() in trained]
    if leaked:
        print("ERROR — eval set leaks training utterances (not held-out):")
        for q in leaked:
            print(f"  - {q}")
        sys.exit(2)


def main() -> None:
    rows = load_eval_set()
    assert_held_out(rows)

    # confusion[true][pred]
    confusion = {t: defaultdict(int) for t in TIERS}
    correct = 0

    for row in rows:
        pred = classify(row["query"])
        gold = row["label"]
        confusion[gold][pred] += 1
        if pred == gold:
            correct += 1
        else:
            print(f"  MISS  gold={gold:<7} pred={pred:<7} | {row['query']}")

    total = len(rows)
    acc = correct / total if total else 0.0

    # ── Confusion matrix ─────────────────────────────────────────────────────
    print("\nConfusion matrix (rows = gold, cols = predicted):")
    header = "            " + "".join(f"{('pred:' + t[:1].upper()):>9}" for t in TIERS)
    print(header)
    for gold in TIERS:
        cells = "".join(f"{confusion[gold][pred]:>9}" for pred in TIERS)
        print(f"  true:{gold:<7}{cells}")

    # ── Per-tier precision / recall ──────────────────────────────────────────
    print("\nPer-tier precision / recall:")
    for t in TIERS:
        tp = confusion[t][t]
        fn = sum(confusion[t][p] for p in TIERS if p != t)
        fp = sum(confusion[g][t] for g in TIERS if g != t)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        print(f"  {t:<8} precision={precision:5.1%}  recall={recall:5.1%}")

    # ── Headline ─────────────────────────────────────────────────────────────
    print(f"\nAccuracy: {acc:.1%} ({correct}/{total})   target: {TARGET:.0%}")
    if acc < TARGET:
        print("RESULT: BELOW TARGET")
        sys.exit(1)
    print("RESULT: PASS")


if __name__ == "__main__":
    main()
