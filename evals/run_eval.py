"""
evals/run_eval.py — Held-out accuracy eval for the complexity classifier.

Scores gateway.classifier.classify() against a hand-labeled, held-out query set
(evals/eval_set.jsonl) that shares ZERO utterances with the routes defined in
classifier.py. Reusing route utterances would fake ~100% accuracy; fresh queries
give an honest generalization number — this is the metric quoted in CLAUDE.md.

Run from the repo root:

    python -m evals.run_eval

Prints overall accuracy, a 3x3 confusion matrix, per-tier precision/recall, and the
confidence distribution. Writes evals/results/run_eval.json — the artifact README
and CLAUDE.md cite as evidence. Exits non-zero if accuracy falls below TARGET
(0.80, the Week-3 bar), so this is the CI gate.

This is the CANONICAL classifier eval. evals/classifier_eval.py is the older Week-3
script running a different 60-query set (evals/testset.py); it is kept working but
only this one has the assert_held_out leakage guard and gates CI.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from gateway.classifier import classify, _TIER_UTTERANCES

# Windows consoles default to cp1252. This script's own output is ASCII, but eval
# queries and future report tweaks may not be — and a UnicodeEncodeError here would
# fail the CI gate for an encoding reason rather than an accuracy one.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TIERS = ["simple", "medium", "complex"]
TARGET = 0.80
EVAL_PATH = Path(__file__).with_name("eval_set.jsonl")
RESULTS_PATH = Path(__file__).with_name("results") / "run_eval.json"


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
    for utterances in _TIER_UTTERANCES.values():
        trained.update(u.strip().lower() for u in utterances)
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
    confidences: list[float] = []
    misses: list[dict] = []

    for row in rows:
        # classify() returns a (tier, confidence) TUPLE — it must be unpacked.
        # Treating the tuple as a str silently breaks every metric: `pred == gold`
        # is always False, and formatting it raises TypeError on the first miss.
        pred, conf = classify(row["query"])
        gold = row["label"]
        confusion[gold][pred] += 1
        confidences.append(conf)
        if pred == gold:
            correct += 1
        else:
            misses.append({"query": row["query"], "expected": gold,
                           "predicted": pred, "confidence": round(conf, 4)})
            print(f"  MISS  gold={gold:<7} pred={pred:<7} conf={conf:.3f} | {row['query']}")

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
    per_class = {}
    for t in TIERS:
        tp = confusion[t][t]
        fn = sum(confusion[t][p] for p in TIERS if p != t)
        fp = sum(confusion[g][t] for g in TIERS if g != t)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
        per_class[t] = {"precision": precision, "recall": recall, "f1": f1,
                        "support": tp + fn}
        print(f"  {t:<8} precision={precision:5.1%}  recall={recall:5.1%}")

    # ── Confidence distribution ──────────────────────────────────────────────
    # classify() divides the semantic-router score sum by 5.0, so this is a
    # RELATIVE score, not a calibrated probability. Printed because a low mean
    # alongside high accuracy is expected here — see CLAUDE.md.
    conf_stats = {}
    if confidences:
        conf_stats = {
            "min": min(confidences),
            "max": max(confidences),
            "mean": sum(confidences) / len(confidences),
        }
        print(f"\nConfidence (relative score, not a probability): "
              f"min={conf_stats['min']:.4f} max={conf_stats['max']:.4f} "
              f"mean={conf_stats['mean']:.4f}")

    # ── Persist the artifact README/CLAUDE.md cite as evidence ───────────────
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps({
        "eval_set": EVAL_PATH.name,
        "accuracy": acc,
        "correct": correct,
        "total": total,
        "target_accuracy": TARGET,
        "passed": acc >= TARGET,
        "per_class": per_class,
        "confusion": {g: {p: confusion[g][p] for p in TIERS} for g in TIERS},
        "confidence": conf_stats,
        "misclassified": misses,
    }, indent=2), encoding="utf-8")
    print(f"Results written -> {RESULTS_PATH}")

    # ── Headline ─────────────────────────────────────────────────────────────
    print(f"\nAccuracy: {acc:.1%} ({correct}/{total})   target: {TARGET:.0%}")
    if acc < TARGET:
        print("RESULT: BELOW TARGET")
        sys.exit(1)
    print("RESULT: PASS")


if __name__ == "__main__":
    main()
