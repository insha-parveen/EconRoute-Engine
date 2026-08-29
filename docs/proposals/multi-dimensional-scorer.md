# Proposal: Multi-dimensional routing scorer

**Status:** REJECTED as implemented — 2026-08-25. Kept as a roadmap item.
**Prototype:** [`scorer_prototype.py`](scorer_prototype.py) (not wired into the gateway)
**Would replace:** the complexity-only tier choice in `gateway/router.py` Step 2

---

## The idea (still sound)

Today the router picks a tier from one signal: the semantic-router complexity label.
A "complex"-labelled prompt might be two words long and cheap to serve; a "simple"
label might sit on top of a 30-turn conversation. Single-dimension routing leaves
money and quality on the table.

The proposal: score every tier across five weighted dimensions and pick the winner.

| # | Dimension | Weight | Purpose |
|---|-----------|--------|---------|
| 1 | Complexity (semantic-router) | 35% | Meaning-based difficulty |
| 2 | Token count | 25% | How well the tier fits the request size |
| 3 | Conversation depth | 15% | Longer chats need more capable models |
| 4 | Latency budget (`X-Latency-Budget-Ms`) | 15% | Honour a caller's latency SLO |
| 5 | Cost budget (`X-Cost-Budget-Usd`) | 10% | Honour a caller's spend ceiling |

Transparent hand-tuned weights, env-overridable, no black-box ML. That part is right.

---

## Why the prototype was rejected

Measured by feeding the scorer a **perfect** classifier — the gold labels from
`evals/eval_set.jsonl` as `classifier_tier` — so every tier change observed is caused
by the scorer alone, not by classifier error.

The classifier's real confidence distribution was measured first, because the scorer's
behaviour depends entirely on it:

```
classifier confidence over 60 held-out queries:
  min=0.1487  max=0.6602  mean=0.3299   (60 distinct values, none saturated)
```

That range is exactly where the scorer misbehaves.

| Probe | Result |
|-------|--------|
| Single-turn, any confidence | **100% agreement** with the classifier — 0/60 tiers changed. Zero routing value on the demo path and the eval path. |
| Multi-turn @ conf 0.2 | 4-message chat `simple`→**medium**; 8-message→**complex**. Escalates on conversation *length alone*. |
| Multi-turn @ conf 0.35 (near the real mean) | 4-msg→medium, 12-msg→complex. |
| `gold=complex`, prompt `"hi"` (0 tokens) | stays **complex** at every confidence — never de-escalates. |

The distortion is **always upward, never downward** — a one-way ratchet toward the
expensive tier. Four concrete defects cause it:

### D1 — `_token_score` is inverted relative to its own comment

The comment says *"higher score for smaller tiers (cheaper)"*. It does the opposite at
every token count:

```
tokens=50    simple=0.985  medium=0.993  complex=0.996   -> favours 'complex'
tokens=800   simple=0.766  medium=0.883  complex=0.941   -> favours 'complex'
tokens=6000  simple=0.000  medium=0.107  complex=0.254   -> favours 'complex'
```

25% of the total weight is a permanent vote for the priciest tier.

### D2 — `_TIER_MAX_TOKENS` measures the wrong quantity

`1024 / 2048 / 4096` are copied from `model_config.py`, where they are the **output
generation caps** — not context windows. All three Groq models hold 128K+ tokens of
context. The scorer therefore compares *input* length against an *output* cap and
declares a 6000-token prompt an overflow for `gpt-oss-20b`, which would serve it fine.

### D3 — `_TIER_COST_RATES` is non-monotone in price

It copies the *theoretical baseline-equivalent* rates from `model_config.py`:

```python
{"simple": 0.00025, "medium": 0.00015, "complex": 0.005}
```

Those are Haiku / GPT-4o-mini / GPT-4o equivalents, and GPT-4o-mini undercuts Haiku.
So "medium" looks cheaper than "simple", and a *tighter* budget routes to the *bigger*
model:

```
budget=$0.0001   simple=0.000  medium=0.500  complex=0.000   -> favours 'medium'
```

### D4 — It corrupts the `classifier_confidence` column

The scorer returns a winner/runner-up *margin ratio*, structurally bounded in
[0.5, 1.0] — measured band 0.50–0.61. `router.py` then did:

```python
classifier_confidence = max(classifier_confidence, scorer_confidence)
```

Since real classifier confidence averages 0.33, that overwrites **nearly every genuine
value** with ~0.55:

```
true conf=0.05 -> logged 0.5337   *** INFLATED ***
true conf=0.35 -> logged 0.5516   *** INFLATED ***
true conf=0.70 -> logged 0.7000
```

Low confidence is the single most useful signal a router has — it marks the queries
worth escalating or reviewing. This floored it away in Postgres, the Streamlit
dashboard, and the WebSocket live feed simultaneously. Two different quantities were
being written to one column.

### D5 — Unmeasurable by construction

`evals/run_eval.py` calls `gateway.classifier.classify()` directly, so the scorer sits
**outside the eval**. Shipping it would have meant the 88.3% headline number no longer
described what actually picks the model.

### D6 — Duplicated source of truth

`_TIER_MAX_TOKENS`, `_TIER_TYPICAL_LATENCY` and `_TIER_COST_RATES` re-declare values
that `providers/model_config.py` owns. CLAUDE.md names that file the single source of
truth for tiers and rates.

---

## What a correct version needs

1. Read tier facts from `providers/model_config.py` — never re-declare them.
2. Separate **context window** from **output cap**; score input length against the
   real context window.
3. Derive cost ordering from actual price, so a tighter budget always prefers cheaper.
4. Fix `_token_score` so a short prompt genuinely favours the cheap tier.
5. Allow **de-escalation**, not just escalation — a two-word "complex" prompt should
   fall to a cheaper tier.
6. Emit `scorer_confidence` as its **own** field. Never overwrite
   `classifier_confidence`; they measure different things.
7. Add `tests/test_scorer.py` (pure, no network — the scorer is pure functions).
8. Add an **end-to-end routing eval** that exercises `route()`, not just `classify()`,
   so the scorer's effect on tier distribution and cost is measured before it ships.

Only then wire the `X-Latency-Budget-Ms` / `X-Cost-Budget-Usd` headers (originally
tracked as suggestion B2) — plumbing them in earlier would just activate D1–D3.

---

## Reproducing the measurements

The probes above used `evals/eval_set.jsonl` gold labels as a stand-in for a perfect
classifier, calling `RoutingScorer.score()` directly. See the defect table for the
expected output of each probe.
