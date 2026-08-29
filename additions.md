# EconRoute — Suggested Additions: review outcome

Review session **2026-08-25**. This file originally recorded a set of proposed
backend/frontend changes plus a claimed implementation status. That status table was
wrong in one important place, so this file now records the **verified** outcome.

Corrected on review: **B1 was marked "✅ Done — integrated into `router.py` as Step 2b".
It was not.** An editor had written the integrated version to `gateway/router` (no
`.py` extension), a file Python never imports. The real `gateway/router.py` imported
`RoutingScorer` and instantiated `_scorer` at module load but **never called it** — AST
check confirmed `_scorer` was referenced only on its own assignment line. The scorer was
dead code, and `routing_reason` still read `classifier · {tier}`. That same edit also
left two duplicated imports wedged around the `_scorer` assignment.

---

## Outcome

| ID | Suggestion | Verdict | Notes |
|----|-----------|---------|-------|
| **B1** | Multi-dimensional routing scorer | ❌ **Rejected as implemented** | Idea kept on the roadmap. Measured against the eval set with a *perfect* classifier: 100% agreement single-turn (no value), and escalation on conversation length alone at the real confidence mean. Evidence + rework plan: [`docs/proposals/multi-dimensional-scorer.md`](docs/proposals/multi-dimensional-scorer.md) |
| **B2** | Read latency/cost budgets from headers | ⛔ **Blocked on B1** | Plumbing headers in would have activated the three inverted dimensions (D1–D3). Do this only after the rework |
| **B3** | Fix Groq-vs-Ollama `max_tokens` | ✅ **Accepted** | `config["max_tokens"]` instead of `GROQ_TIERS[tier]["max_tokens"]`. Verified `OLLAMA_TIERS` defines `max_tokens` on all three tiers, so no `KeyError`. Values match per tier today — this removes a latent bug rather than changing behaviour |
| **B4** | Don't store raw prompts in Redis | ✅ **Accepted, claim softened** | Verified nothing reads the field: `find_match` touches only `embedding` and `response`, both via `.get()`, so pre-change entries stay valid and expire within the 1h TTL. Reworded from "never raw text / PII-safe" to **"no plaintext prompt at rest"** — the 384-dim embedding is still stored and embeddings are partially invertible, so this is defence in depth, not anonymisation |
| **B5** | Sync startup logs / schema examples | ✅ **Accepted** | `llama-3.1-8b-instant` is deprecated and `deepseek-r1-distill` decommissioned; the log and schema example now match `model_config.py` |
| **F1** | Show the LLM response in the hero demo | ✅ **Accepted, hardened** | Type-checks (`choices` was already on `ChatResponse`, `latency_ms` non-optional). Added optional chaining — the response is an unvalidated `as ChatResponse` cast, so an empty `choices[]` would throw *during render* and escape the component's error state to the Next error boundary |
| **F2** | PII-safe live feed | ✅ **Already satisfied** | No work needed. `LiveEvent` has no prompt field; `query_id` appears only as a React key and is never rendered. Verified by grep across `frontend/` |

---

## Independent findings from the same review

Not in the original proposal list, found while verifying it. Ranked by impact.

| Finding | Status |
|---------|--------|
| **`python -m evals.run_eval` crashed — the headline metric was unreproducible.** `classify()` returns `(tier, confidence)`; both eval scripts treated it as a `str`, so `pred == gold` was always False and the script died on the first miss with `TypeError: unsupported format string passed to tuple.__format__`. `classifier_eval.py` had the same bug but failed *silently* (every row skipped → 0%, exit 1) | ✅ Fixed. Both scripts unpack the tuple. **The 88.3% is real: 53/60, reproduced.** |
| README claimed **90%** citing `evals/results/classifier_eval.json` — a stale 2026-07-05 artifact with a different confusion matrix and misclassified queries not in the current eval set | ✅ README corrected to 88.3% + per-tier table; now cites `run_eval.json`, regenerated every run |
| Neither eval ran in CI — which is why the crash went unnoticed. `ruff` also skipped `evals/` and `websocket/` | ✅ `run_eval.py` gates CI at 0.80 and uploads its artifact; ruff extended |
| `_query_id` sliced `[:8]` in `cache.py` but `[:16]` in `router.py`, despite a docstring claiming they mirror — cache logs and Postgres rows could not be joined on `query_id`, the entire reason the hash exists | ✅ Aligned on `[:16]` (preserves existing DB rows) |
| **`route()` has no test** — the most important function in the codebase | ⏳ Open, highest-value gap |
| **No end-to-end routing eval** — `run_eval.py` measures `classify()` in isolation. Nothing measures tier distribution or realised savings through `route()`. This is precisely why the scorer got built and nearly shipped without its cost impact being visible | ⏳ Open |
| Classifier confidence is uncalibrated — magic `/5.0` divisor, hardcoded `0.85` fallback. Measured range 0.149–0.660, mean 0.330, alongside 88.3% accuracy | ⏳ Open, documented in CLAUDE.md |
| A few eval labels are arguable, e.g. `"Translate 'good morning, how are you?' into Spanish"` labelled `medium` | ⏳ Open |
| README rendered `architecture.png` twice (as video thumbnail and again below) | ✅ Deduped; demo is now a badge link |

---

## Method note

The B1 verdict came from measurement, not reading. The scorer was fed the **gold labels
from `evals/eval_set.jsonl` as its classifier input** — a perfect upstream classifier —
so every tier change observed was attributable to the scorer alone. The classifier's
real confidence distribution was measured first, because the scorer's behaviour is
entirely conditional on it. Full numbers in the proposal doc.
