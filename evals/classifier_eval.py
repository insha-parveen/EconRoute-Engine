"""
evals/classifier_eval.py — Accuracy eval for the semantic-router complexity classifier.

Week 3 exit bar: classifier must reach >80% accuracy on held-out queries.
This script is the proof. It runs the REAL production classifier
(gateway.classifier.classify) against the held-out TEST_SET in evals/testset.py,
computes accuracy + per-class precision/recall/F1 + a confusion matrix, prints a
readable report, writes a results JSON for the Week 4 dashboard, and exits non-zero
if accuracy is below the target — so it doubles as a CI gate.

Runs fully offline: classify() uses the local all-MiniLM-L6-v2 encoder. No Groq
key, no Redis, no network needed.

Usage (from repo root):
    python -m evals.classifier_eval

Metrics are hand-rolled with the stdlib — no sklearn. It's just counting, and
keeping the dependency surface small matters more than saving 30 lines.
"""

import json
import logging
import os
import sys

from gateway.classifier import classify
from evals.testset import TEST_SET

logging.basicConfig(level=logging.WARNING)  # quiet the classifier's INFO chatter
logger = logging.getLogger(__name__)

TARGET_ACCURACY = 0.80
TIERS = ("simple", "medium", "complex")

_RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
_RESULTS_PATH = os.path.join(_RESULTS_DIR, "classifier_eval.json")


# ─── Run ──────────────────────────────────────────────────────────────────────

def run_eval(test_set: list[tuple[str, str]]) -> dict:
    """
    Classify every query in the test set and compute metrics.

    Returns a dict with:
        accuracy         : float — overall correct / total
        correct, total   : ints
        per_class        : {tier: {precision, recall, f1, support}}
        confusion        : {actual_tier: {predicted_tier: count}}
        misclassified    : [{query, expected, predicted}]
        passed           : bool — accuracy >= TARGET_ACCURACY
    """
    # confusion[actual][predicted] = count
    confusion = {a: {p: 0 for p in TIERS} for a in TIERS}
    misclassified: list[dict] = []
    correct = 0

    for query, expected in test_set:
        predicted = classify(query)

        # Defensive: classify() should only ever return a valid tier, but a bad
        # return would silently corrupt the confusion matrix — surface it instead.
        if predicted not in TIERS or expected not in TIERS:
            logger.warning("Skipping row with unexpected label: exp=%s pred=%s q=%r",
                           expected, predicted, query)
            continue

        confusion[expected][predicted] += 1
        if predicted == expected:
            correct += 1
        else:
            misclassified.append(
                {"query": query, "expected": expected, "predicted": predicted}
            )

    total = sum(confusion[a][p] for a in TIERS for p in TIERS)
    accuracy = correct / total if total else 0.0

    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "per_class": _per_class_metrics(confusion),
        "confusion": confusion,
        "misclassified": misclassified,
        "passed": accuracy >= TARGET_ACCURACY,
        "target_accuracy": TARGET_ACCURACY,
    }


def _per_class_metrics(confusion: dict) -> dict:
    """
    Compute precision / recall / F1 / support per tier from the confusion matrix.

      precision(t) = correctly predicted t / everything predicted t
      recall(t)    = correctly predicted t / everything actually t
      f1(t)        = harmonic mean of the two
      support(t)   = number of test queries actually labeled t
    """
    metrics = {}
    for t in TIERS:
        tp = confusion[t][t]
        predicted_t = sum(confusion[a][t] for a in TIERS)   # column sum
        actual_t = sum(confusion[t][p] for p in TIERS)      # row sum

        precision = tp / predicted_t if predicted_t else 0.0
        recall = tp / actual_t if actual_t else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)

        metrics[t] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": actual_t,
        }
    return metrics


# ─── Report ───────────────────────────────────────────────────────────────────

def print_report(results: dict) -> None:
    """Print a human-readable eval report to stdout."""
    acc = results["accuracy"]
    passed = results["passed"]
    target = results["target_accuracy"]

    print()
    print("=" * 60)
    print("  EconRoute — Classifier Accuracy Eval (Week 3)")
    print("=" * 60)
    print(f"  Overall accuracy : {acc:6.1%}  "
          f"({results['correct']}/{results['total']})")
    print(f"  Target           : {target:6.1%}")
    status = "PASS ✅" if passed else "FAIL ❌"
    print(f"  Result           : {status}")
    print("-" * 60)

    # Per-class table
    print("  Per-class metrics")
    print(f"    {'tier':<9}{'precision':>11}{'recall':>9}{'f1':>8}{'support':>9}")
    for t in TIERS:
        m = results["per_class"][t]
        print(f"    {t:<9}{m['precision']:>11.2f}{m['recall']:>9.2f}"
              f"{m['f1']:>8.2f}{m['support']:>9}")
    print("-" * 60)

    # Confusion matrix (rows = actual, cols = predicted)
    print("  Confusion matrix  (rows = actual, cols = predicted)")
    header = "actual \\ pred"
    print(f"    {header:<14}" + "".join(f"{t:>9}" for t in TIERS))
    for a in TIERS:
        row = results["confusion"][a]
        print(f"    {a:<14}" + "".join(f"{row[p]:>9}" for p in TIERS))
    print("-" * 60)

    # Misclassifications — the tuning signal when accuracy is low
    mis = results["misclassified"]
    if mis:
        print(f"  Misclassified ({len(mis)}):")
        for row in mis:
            print(f"    [{row['expected']:>7} → {row['predicted']:<7}] {row['query']}")
    else:
        print("  Misclassified: none 🎉")
    print("=" * 60)
    print()


# ─── Persist ──────────────────────────────────────────────────────────────────

def write_results(results: dict, path: str = _RESULTS_PATH) -> None:
    """Write results JSON for the Week 4 dashboard to consume."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"  Results written → {path}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> int:
    results = run_eval(TEST_SET)
    print_report(results)
    write_results(results)
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
