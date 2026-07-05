"""
evals/testset.py — Held-out labeled test set for the complexity classifier.

CRITICAL — held-out means held-out:
  Every query below is HAND-WRITTEN and does NOT appear in the utterance lists
  in gateway/classifier.py. The classifier's SemanticRouter is built from those
  utterances; if we tested it on the same strings it was built from, accuracy
  would be a meaningless ~100%. These are fresh phrasings, novel topics, and
  paraphrases the classifier has never "seen" — the only honest way to measure
  generalization.

Label rationale (must match classifier.py's route design):
  simple  = factual lookups, definitions, single-fact / yes-no / conversions
            → short output, no reasoning chain
  medium  = explanations, comparisons, summaries, translations, conceptual how-to
            → paragraph-length output, some reasoning
  complex = code generation, debugging, design/architecture, long-form writing,
            deep analysis
            → long output, multi-step reasoning, quality matters

Coverage: ~20 per tier, spread across domains (tech, science, history,
everyday, math/finance, language) so we don't overfit the metric to one topic.
"""

# (query, expected_tier) — expected_tier ∈ {"simple", "medium", "complex"}
TEST_SET: list[tuple[str, str]] = [
    # ─── SIMPLE — factual lookups, definitions, single-fact / yes-no / conversions ─
    ("What is the capital of Japan?", "simple"),
    ("Who wrote Romeo and Juliet?", "simple"),
    ("What does CPU stand for?", "simple"),
    ("Define photosynthesis", "simple"),
    ("What is the speed of light?", "simple"),
    ("How many continents are there?", "simple"),
    ("What is 15 times 4?", "simple"),
    ("Convert 5 kilometers to miles", "simple"),
    ("Is water a compound?", "simple"),
    ("What year did the Berlin Wall fall?", "simple"),
    ("What is the chemical symbol for gold?", "simple"),
    ("Who painted the Mona Lisa?", "simple"),
    ("What does JSON stand for?", "simple"),
    ("How do you spell 'accommodate'?", "simple"),
    ("What is the largest planet in our solar system?", "simple"),
    ("Define inflation", "simple"),
    ("What is the freezing point of water in Celsius?", "simple"),
    ("Is a tomato a fruit or a vegetable?", "simple"),
    ("What is the population of Canada?", "simple"),
    ("What does GPU mean?", "simple"),

    # ─── MEDIUM — explanations, comparisons, summaries, translations, how-to ──────
    ("Explain how a car engine works", "medium"),
    ("What is the difference between HTTP and HTTPS?", "medium"),
    ("Summarize the plot of Hamlet", "medium"),
    ("Compare cats and dogs as pets", "medium"),
    ("How does vaccination protect the body?", "medium"),
    ("Explain the water cycle", "medium"),
    ("What are the advantages and disadvantages of remote work?", "medium"),
    ("Translate 'good morning, how are you' into Spanish", "medium"),
    ("How does compound interest work?", "medium"),
    ("What is the difference between weather and climate?", "medium"),
    ("Give me an overview of the solar system", "medium"),
    ("Explain how Wi-Fi transmits data", "medium"),
    ("Compare electric cars and gasoline cars", "medium"),
    ("What is the best way to prepare for a job interview?", "medium"),
    ("How should I organize my weekly schedule to be productive?", "medium"),
    ("Explain the causes of the American Civil War", "medium"),
    ("What are the differences between RAM and an SSD?", "medium"),
    ("Summarize how the stock market works", "medium"),
    ("How does a refrigerator keep food cold?", "medium"),
    ("What are the pros and cons of learning a second language?", "medium"),

    # ─── COMPLEX — code, debugging, design, long-form writing, deep analysis ──────
    ("Write a Python function that reverses a string", "complex"),
    ("Implement a stack data structure in Java", "complex"),
    ("Create a function to check if a number is prime in C++", "complex"),
    ("Write a SQL query that joins orders and customers by id", "complex"),
    ("My recursive function causes a stack overflow — help me fix it", "complex"),
    ("Debug this JavaScript that returns undefined instead of the sum", "complex"),
    ("Design a scalable notification system for a mobile app", "complex"),
    ("Architect a caching layer for a high-traffic web service", "complex"),
    ("Design a database schema for a hospital management system", "complex"),
    ("Write a detailed essay on the ethics of artificial intelligence", "complex"),
    ("Write a comprehensive analysis of the 2008 financial crisis", "complex"),
    ("Write a technical guide to setting up a Kubernetes cluster", "complex"),
    ("Analyze the space and time complexity of merge sort", "complex"),
    ("Explain the trade-offs between REST and GraphQL in depth", "complex"),
    ("Refactor this nested loop into a more efficient algorithm", "complex"),
    ("Build a REST endpoint in Flask that handles file uploads", "complex"),
    ("Write a regular expression to validate email addresses and explain it", "complex"),
    ("Compare and critique three consensus algorithms for distributed systems", "complex"),
    ("Design an event-driven architecture for an e-commerce checkout flow", "complex"),
    ("Write a multithreaded producer-consumer program in Python", "complex"),
]
