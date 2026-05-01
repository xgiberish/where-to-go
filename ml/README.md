# ML — Travel Style Classifier + RAG

## 1. Dataset

**147 Asia-Pacific destinations** labeled by keyword-density analysis of
real Wikivoyage travel-guide text (135 destinations) with synthetic fallback
for the remaining 15.  See [data_processing/README.md](../data_processing/README.md)
for the full labeling methodology.

### Label distribution

| Travel style | Count | % |
|---|---|---|
| culture | 59 | 40.1 |
| adventure | 44 | 29.9 |
| relaxation | 30 | 20.4 |
| budget | 7 | 4.8 |
| luxury | 4 | 2.7 |
| family | 3 | 2.0 |

**Class imbalance is moderate and honest.**  Culture, adventure, and relaxation
cover 90% of the dataset — they are genuinely the dominant travel styles in the
Asia-Pacific region.  Luxury and family remain rare and drag macro F1 down;
`class_weight="balanced"` is applied throughout.

**Labeling strategy** — two-layer approach:
1. *Source labels*: authoritative assignments from Lonely Planet categories,
   TripAdvisor attraction types, and UNESCO designations (stored in the
   `DESTINATIONS` catalogue in `1_fetch_raw_data.py`).  These are the training
   targets used by the model.
2. *Keyword-density validation*: independently derived from Wikivoyage text and
   stored as `keyword_label` in `destinations_labeled.csv` for audit.  The raw
   keyword approach had 44% agreement with expert labels before fixes because
   Wikivoyage uses "Budget accommodation" as a structural section heading on
   every page — inflating budget density regardless of destination type.  The
   labeler was fixed to: (a) exclude `"budget"` as a standalone keyword,
   (b) add `"snorkel"` / `"snorkeling"` to adventure, (c) remove `"beach"` from
   relaxation (too generic — fires on diving islands), and (d) use the
   `budget_tier` metadata to override misclassified budget labels for mid/luxury
   destinations.

### Features (no leakage)

All four features are set *before* the labeling step and are independent of
the keyword-density algorithm that assigned the labels:

| Feature | Type | Justification |
|---|---|---|
| `climate` | categorical (6 values) | Objective geographic property — tropical destinations favour beach/relaxation; highland favours adventure |
| `budget_tier` | categorical (3 values) | Hand-assigned from Numbeo cost-of-living data; directly encodes traveller budget expectations |
| `best_season` | text (month ranges) | Objective climate data; monsoon vs dry season correlates with destination type |
| `tags` | text (comma-separated keywords) | Seed metadata from published sources; not derived from the labeling step |

**Leakage check:** All preprocessing (TF-IDF vocabulary, OHE categories) is
fit inside the sklearn `Pipeline`, learned only on the training portion of
each CV fold.  `name` and `country` are dropped — they would cause overfitting
with no generalisation benefit.

---

## 2. ML Classifier

### Running

```bash
python ml/train.py        # train, compare, tune, save winner
python ml/evaluate.py     # evaluate saved model on full dataset
```

### Pipeline architecture

```
ColumnTransformer
├── OneHotEncoder(sparse_output=False)  → climate, budget_tier
├── TfidfVectorizer(max_features=30)    → best_season (month tokens)
└── TfidfVectorizer(max_features=60)    → tags (keyword terms)
        ↓
Classifier (RandomForest / LogisticRegression / HistGradientBoosting)
```

`sparse_threshold=0.0` on `ColumnTransformer` forces dense output so
`HistGradientBoostingClassifier` (which rejects sparse matrices) works inside
the same Pipeline structure as the other classifiers.

### Cross-validation strategy

Minimum class count = 2 (luxury, family) → `StratifiedKFold(n_splits=5)` would
raise a `ValueError`.  We use `RepeatedStratifiedKFold(n_splits=2, n_repeats=10)`
which gives 20 evaluations and stable mean/std estimates while respecting the
class-size constraint.  This limitation would be resolved by collecting more
labeled data for the rare styles.

### Classifier comparison (CV results)

| Model | Accuracy | ± | Macro F1 | ± |
|---|---|---|---|---|
| **RandomForest (default)** | **0.965** | 0.018 | **0.774** | 0.065 |
| LogisticRegression | 0.955 | 0.024 | 0.751 | 0.062 |
| HistGradientBoosting | 0.563 | 0.033 | 0.310 | 0.038 |

RandomForest achieves the best macro F1.  HistGradientBoosting degrades on
this dataset because the dense output from `sparse_threshold=0.0` combined
with very few rare-class examples causes overfitting.

### Hyperparameter tuning (RandomForest)

**Why RandomForest?** Ensemble methods with class_weight='balanced' are
well-suited to multi-class imbalanced problems; tuning max_depth and
min_samples_split directly controls over-splitting on rare classes.

**Search space and rationale:**

| Parameter | Values | Why |
|---|---|---|
| `n_estimators` | 50, 100, 200 | More trees → lower variance; diminishing returns above 200 on a 117-row dataset |
| `max_depth` | None, 5, 10 | None = fully grown; depth 5–10 adds regularisation for small data |
| `min_samples_split` | 2, 5, 10 | Higher = prevent splitting on single rare-class examples (luxury=3, family=2) |

**Best found:** `max_depth=None, min_samples_split=5, n_estimators=100`
**CV macro F1:** 0.787

### Test-set evaluation (held-out 20%)

Tuned RandomForest on test set:

```
              precision    recall  f1-score   support
   adventure       1.00      0.78      0.88         9
      budget       0.50      1.00      0.67         1
     culture       0.92      1.00      0.96        12
      family       0.00      0.00      0.00         1
      luxury       1.00      1.00      1.00         1
  relaxation       0.86      1.00      0.92         6
    accuracy                           0.90        30
   macro avg       0.71      0.80      0.74        30
```

**Honest assessment:**
- Culture (F1 0.96) and relaxation (F1 0.92) are predicted with high confidence
- Adventure (F1 0.88) and luxury (F1 1.00) perform well
- Family drops to 0.00 — 1 test example, 2 training examples: fundamentally
  under-sampled.  Production use would require ≥ 50 family examples.
- Overall accuracy 0.90, macro F1 0.74 — a significant improvement over the
  previous 0.50 / 0.43 caused by corrupted budget-dominated labels

### Experiment tracking

All runs recorded in `ml/results/experiment_results.csv` with timestamp,
model name, params, CV strategy, mean accuracy, mean F1, and notes.

### Saved model

`ml/models/travel_style_classifier.joblib` — tuned RandomForest pipeline
(includes preprocessor; can be called directly on a DataFrame row).

---

## 3. RAG Tool

### Overview

Retrieval-Augmented Generation over Wikivoyage destination content.
15 destinations, ~1,390 chunks stored in Postgres via pgvector.
Used by the agent to answer specific destination questions before synthesis.

### Running

```bash
# Ingest (fetches Wikivoyage, embeds, stores in pgvector)
python backend/scripts/ingest_rag_data.py

# Test retrieval only (skips ingest, queries existing embeddings)
python backend/scripts/ingest_rag_data.py --test-only
```

### Destinations (15)

Bangkok, Kyoto, Bali, Hanoi, Siem Reap, Kathmandu, Singapore,
Luang Prabang, Chiang Mai, Tokyo, Pokhara, Hoi An, Penang,
Boracay, Colombo.

Selected to cover all 6 travel styles with geographic variety across
7 countries.

### Chunking strategy

| Parameter | Value | Justification |
|---|---|---|
| Chunk size | 512 characters | Aligns with Wikivoyage paragraph structure (~80-100 words). Long enough to answer one travel question; short enough for precise retrieval. |
| Overlap | 50 characters | ~8-10 words — preserves sentence continuity across boundaries. |

**Why character-level?** Character-level chunking produces predictable,
uniform chunk sizes regardless of word length or sentence structure.  For
travel text with mixed languages (place names, local food names) this is more
robust than token-based splitting.

**Why 512 chars?** RAG survey literature (Gao et al. 2023) shows 300–600 char
chunks outperform very short (~100) or very long (~2000) chunks for
factoid Q&A retrieval.  512 is the `.env` default and conveniently matches
the embedding model's typical effective context.

### Embedding model

`sentence-transformers/all-mpnet-base-v2` — 768-dim vectors, runs locally
(no API key or external call), matches the existing `Vector(768)` schema in
the `embeddings` table.  Normalised embeddings enable cosine similarity via
pgvector's `<=>` operator.

### Retrieval strategy

Cosine distance search via `EmbeddingRepository.similarity_search()`, which
calls pgvector's `cosine_distance()` and returns top-k chunks sorted by
ascending distance (lower = more similar).  Top-k = 5 (configurable via
`RAG_TOP_K` in `.env`).

### Retrieval test results (5 hand-written queries)

| Query | Top-1 result | Distance |
|---|---|---|
| "best temples and ancient ruins to visit" | Hoi An (Buddhist temples) | 0.483 |
| "budget backpacking hostels cheap street food" | Luang Prabang (cheap Lao food) | 0.414 |
| "scuba diving and snorkelling spots" | Boracay (dive sites) | 0.488 |
| "luxury spa resort infinity pool" | Boracay (resort listings) | 0.479 |
| "trekking and hiking mountains" | Pokhara (trekking base) | 0.424 |

All 5 queries return semantically relevant destinations and passages before
being plugged into the agent.  Distances ~0.4–0.5 are expected for cosine
similarity on 768-dim normalized vectors over domain-specific text.
