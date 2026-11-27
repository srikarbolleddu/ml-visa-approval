"""Reproducible training: download the pinned dataset → clean → compare imbalance strategies → write
artifacts.

    uv run python training/train.py

Writes:
  app/model_artifacts/model.skops, manifest.json, samples.json, metrics.json, explore.json
  reports/metrics.json      held-out metrics -- the only source for numbers quoted anywhere
  reports/explore.json      precomputed data for the demo's interactive "Explore" charts
  reports/golden.json       fixed inputs + expected outputs, checked by tests/test_golden.py
  reports/figures/*.png     charts for the README / case study / blog

Method follows the UT Austin PGP-AIML EasyVisa project (gradient boosting on an imbalanced
certified/denied outcome, comparing oversampling and undersampling), rebuilt on public DOL data.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTENC
from imblearn.under_sampling import RandomUnderSampler
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import model as model_io  # noqa: E402
from app.features import (  # noqa: E402
    CATEGORICAL_FEATURES,
    FEATURE_ORDER,
    FIELDS,
    FIELDS_BY_NAME,
    NUMERIC_FEATURES,
    TARGET,
    clean_raw,
    records_to_frame,
)

DATA_URL = (
    "https://www.dol.gov/sites/dolgov/files/ETA/oflc/pdfs/PERM_Disclosure_Data_FY2024_Q4.xlsx"
)
DATA_SHA256 = "57fd1d69396113d04f1a02bb05baa3c0c1f2a393e3ad6bb9b69fa2b55291bee2"
CACHE = ROOT / ".data" / "PERM_Disclosure_Data_FY2024_Q4.xlsx"
# Reading the 76 MB workbook takes about a minute; keep only the columns we use, as CSV.
COLUMNS_CACHE = ROOT / ".data" / "perm_fy2024_columns.csv"
RAW_COLUMNS = sorted(
    {f.source_column for f in FIELDS}
    | {"CASE_STATUS", "WAGE_OFFER_UNIT_OF_PAY", "PW_UNIT_OF_PAY", "REQUIRED_EXPERIENCE"}
)
SEED = 42
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

STRATEGIES = ("No rebalancing", "Class weights", "Random undersampling", "SMOTE")
# (learning_rate, max_leaf_nodes)
GRID = [(0.05, 31), (0.1, 15), (0.1, 31), (0.1, 63), (0.2, 31), (0.2, 63)]


def fetch_dataset() -> pd.DataFrame:
    if COLUMNS_CACHE.exists():
        return pd.read_csv(COLUMNS_CACHE, dtype=str)
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {DATA_URL}")
        # DATA_URL is a constant https URL and the payload is checksum-verified below.
        with urllib.request.urlopen(DATA_URL, timeout=300) as response:  # nosec B310
            CACHE.write_bytes(response.read())
    digest = hashlib.sha256(CACHE.read_bytes()).hexdigest()
    if digest != DATA_SHA256:
        raise SystemExit(f"dataset checksum mismatch: {digest} != {DATA_SHA256}")
    print("reading workbook (about a minute)")
    raw = pd.read_excel(CACHE, engine="openpyxl", usecols=RAW_COLUMNS, dtype=str)
    raw.to_csv(COLUMNS_CACHE, index=False, quoting=csv.QUOTE_NONNUMERIC)
    return raw


def build_prep() -> ColumnTransformer:
    # Fixed category order from FIELDS, so encodings never depend on what the data happens to hold.
    encoder = OrdinalEncoder(
        categories=[list(FIELDS_BY_NAME[n].options) for n in CATEGORICAL_FEATURES],
        handle_unknown="use_encoded_value",
        unknown_value=np.nan,
    )
    return ColumnTransformer(
        [("cat", encoder, CATEGORICAL_FEATURES), ("num", "passthrough", NUMERIC_FEATURES)]
    )


def build_model(strategy: str, learning_rate: float, leaves: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=learning_rate,
        max_leaf_nodes=leaves,
        max_iter=300,
        early_stopping=False,
        l2_regularization=1.0,
        categorical_features=[True] * len(CATEGORICAL_FEATURES) + [False] * len(NUMERIC_FEATURES),
        class_weight="balanced" if strategy == "Class weights" else None,
        random_state=SEED,
    )


def resample(strategy: str, x_enc: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Rebalance the *training* data only. Validation and test keep the real denial rate."""
    if strategy == "Random undersampling":
        sampler: Any = RandomUnderSampler(sampling_strategy=0.5, random_state=SEED)
    elif strategy == "SMOTE":
        # SMOTE-NC: interpolates numbers, takes the most common neighbour value for categories.
        sampler = SMOTENC(
            categorical_features=list(range(len(CATEGORICAL_FEATURES))),
            sampling_strategy=0.5,
            random_state=SEED,
        )
    else:
        return x_enc, y
    x_res, y_res = sampler.fit_resample(x_enc, y)
    return np.asarray(x_res), np.asarray(y_res)


def fit(
    strategy: str, learning_rate: float, leaves: int, x: pd.DataFrame, y: pd.Series
) -> Pipeline:
    prep = build_prep().fit(x)
    x_res, y_res = resample(strategy, prep.transform(x), y.to_numpy())
    model = build_model(strategy, learning_rate, leaves).fit(x_res, y_res)
    return Pipeline([("prep", prep), ("model", model)])


def proba(pipeline: Pipeline, x: pd.DataFrame) -> np.ndarray:
    """P(denied)."""
    return pipeline.predict_proba(x)[:, 1]


def scores(y_true: pd.Series, p: np.ndarray, threshold: float = 0.5) -> dict[str, float]:
    pred = (p >= threshold).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y_true, pred)), 4),
        "recall": round(float(recall_score(y_true, pred)), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, p)), 4),
        "pr_auc": round(float(average_precision_score(y_true, p)), 4),
        "brier": round(float(brier_score_loss(y_true, p)), 4),
        "mean_predicted_risk": round(float(p.mean()), 4),
    }


def tuned_threshold(y_true: pd.Series, p: np.ndarray) -> float:
    """Cutoff maximizing validation F1 for denials (0.5 is meaningless at a 5% base rate)."""
    grid = np.round(np.linspace(0.02, 0.98, 97), 2)
    return float(max(grid, key=lambda t: f1_score(y_true, (p >= t).astype(int))))


def bucket_rates(
    values: pd.Series, y: pd.Series, edges: list[float], labels: list[str]
) -> list[dict[str, Any]]:
    buckets = pd.cut(values, bins=edges, labels=labels, include_lowest=True)
    rates = y.groupby(buckets, observed=False).mean()
    return [{"label": str(k), "value": round(float(v), 4)} for k, v in rates.items()]


def pick(frame: pd.DataFrame, position: int) -> pd.DataFrame:
    """One row by position in an already-sorted frame."""
    return frame.iloc[position : position + 1]


def main() -> None:
    df = clean_raw(fetch_dataset())
    x, y = df[FEATURE_ORDER], df[TARGET]
    # 60/20/20 stratified: train fits, validation chooses, test is touched once at the end.
    x_train, x_rest, y_train, y_rest = train_test_split(
        x, y, test_size=0.4, stratify=y, random_state=SEED
    )
    x_val, x_test, y_val, y_test = train_test_split(
        x_rest, y_rest, test_size=0.5, stratify=y_rest, random_state=SEED
    )
    print(f"rows: train={len(x_train)} val={len(x_val)} test={len(x_test)}")

    # Per strategy: pick learning rate / tree size on validation PR-AUC (ranking quality for the
    # rare "denied" class, independent of any cutoff), then tune the cutoff on validation too.
    candidates: dict[str, Pipeline] = {}
    params: dict[str, dict[str, float]] = {}
    for strategy in STRATEGIES:
        best, best_score = None, -1.0
        for learning_rate, leaves in GRID:
            candidate = fit(strategy, learning_rate, leaves, x_train, y_train)
            score = float(average_precision_score(y_val, proba(candidate, x_val)))
            if score > best_score:
                best, best_score = candidate, score
                params[strategy] = {"learning_rate": learning_rate, "max_leaf_nodes": leaves}
        if best is None:
            raise RuntimeError(f"no model for {strategy}")
        candidates[strategy] = best
        print(f"{strategy}: val PR-AUC {best_score:.4f} {params[strategy]}")

    thresholds = {s: tuned_threshold(y_val, proba(p, x_val)) for s, p in candidates.items()}
    comparison: dict[str, dict[str, Any]] = {
        s: {
            **params[s],
            "threshold": thresholds[s],
            "train": scores(y_train, proba(p, x_train), thresholds[s]),
            "validation": scores(y_val, proba(p, x_val), thresholds[s]),
            "test": scores(y_test, proba(p, x_test), thresholds[s]),
        }
        for s, p in candidates.items()
    }
    final_name = max(STRATEGIES, key=lambda s: comparison[s]["validation"]["pr_auc"])
    final = candidates[final_name]
    threshold = thresholds[final_name]
    test_p = proba(final, x_test)
    tn, fp, fn, tp = (int(v) for v in confusion_matrix(y_test, test_p >= threshold).ravel())

    # Permutation importance on validation: how much PR-AUC drops when a feature is shuffled.
    perm: Any = permutation_importance(
        final, x_val, y_val, scoring="average_precision", n_repeats=5, random_state=SEED
    )
    labels = {f.name: f.label for f in FIELDS}
    importance_rows = sorted(
        (
            {"field": n, "label": labels[n], "importance": round(float(v), 4)}
            for n, v in zip(FEATURE_ORDER, perm.importances_mean, strict=True)
        ),
        key=lambda r: -float(r["importance"]),
    )

    # "Typical application" for the what-if explanations: medians and most common values.
    baseline: dict[str, Any] = {n: float(x_train[n].median()) for n in NUMERIC_FEATURES}
    baseline.update({n: str(x_train[n].mode().iloc[0]) for n in CATEGORICAL_FEATURES})

    model_params = final.named_steps["model"].get_params()
    params_hash = hashlib.sha256(str(sorted(model_params.items())).encode()).hexdigest()[:8]
    model_version = f"gbm-{final_name.lower().replace(' ', '-')}-{params_hash}"
    artifacts = model_io.ARTIFACT_DIR
    artifacts.mkdir(parents=True, exist_ok=True)
    model_io.save(final, model_io.MODEL_PATH)
    manifest = {
        "model_version": model_version,
        "model": f"Gradient boosting ({final_name.lower()})",
        "params": params[final_name],
        "denial_threshold": threshold,
        "baseline": baseline,
        "dataset": {"url": DATA_URL, "sha256": DATA_SHA256, "license": "Public domain (US DOL)"},
    }
    (artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # Curated demo samples: real held-out applications, both outcomes, chosen deterministically.
    t = x_test.assign(actual=y_test.to_numpy(), p=test_p)
    ok, no = t[t.actual == 0].sort_values("p"), t[t.actual == 1].sort_values("p")
    tech = ok[(ok.occupation_group == "15") & (ok.visa_class == "H-1B")]
    small = ok[ok.employer_size < 50]
    low_wage_small = no[(no.employer_size < 100) & (no.annual_wage < 40_000)]
    same_employer = no[no.experience_with_employer == "Y"]
    wrongly_flagged = ok[ok.p >= threshold]
    missed = no[no.p < threshold]
    wanted = [
        ("Certified: tech job on an H-1B", tech, 0.5),
        ("Certified: small company", small, 0.5),
        ("Certified, though the model flagged it", wrongly_flagged, 0.5),
        ("Denied: low wage, small employer", low_wage_small, 1.0),
        ("Denied: experience gained at the same employer", same_employer, 1.0),
        ("Denied, but the model missed it", missed, 1.0),
    ]
    # One application per example (the groups overlap): take the row nearest the wanted position
    # (0.5 = a typical case, 1.0 = the one the model is most sure about) that isn't used yet.
    used: set[Any] = set()
    picks: list[tuple[str, pd.DataFrame]] = []
    for title, group, position in wanted:
        free = group.drop(index=[i for i in group.index if i in used])
        row = pick(free, min(int(len(free) * position), len(free) - 1)) if len(free) else free
        if not row.empty:
            used.add(row.index[0])
        picks.append((title, row))
    samples: list[dict[str, Any]] = []
    for title, row in picks:
        if row.empty:
            continue
        record = row.iloc[0]
        inputs: dict[str, Any] = {}
        for name in FEATURE_ORDER:
            value = record[name]
            if name in NUMERIC_FEATURES:
                value = round(float(value), 1)
                value = int(value) if value.is_integer() else value
            inputs[name] = value
        samples.append(
            {"title": title, "inputs": inputs, "actual": "denied" if record.actual else "certified"}
        )
    (artifacts / "samples.json").write_text(json.dumps(samples, indent=2) + "\n")

    REPORTS.mkdir(exist_ok=True)
    metrics = {
        "dataset": {
            "name": "US DOL OFLC PERM disclosure data, FY2024",
            "rows": len(df),
            "positive_rate": round(float(y.mean()), 4),
            "positive_class": "denied",
            "split": {"train": len(x_train), "validation": len(x_val), "test": len(x_test)},
            "excluded_columns": [
                "personal and contact details",
                "worker nationality / birth country (fairness)",
                "dates and processing fields (not known when filing)",
            ],
        },
        "final_model": final_name,
        "threshold": threshold,
        "test": comparison[final_name]["test"],
        "test_confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "comparison": comparison,
        "model_version": model_version,
    }
    (REPORTS / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    sweep = []
    for cut in np.round(np.linspace(0.05, 0.95, 19), 2):
        s_tn, s_fp, s_fn, s_tp = (int(v) for v in confusion_matrix(y_test, test_p >= cut).ravel())
        sweep.append({"threshold": float(cut), "tn": s_tn, "fp": s_fp, "fn": s_fn, "tp": s_tp})

    visa_options = FIELDS_BY_NAME["visa_class"].to_schema()["options"]
    explore = {
        "strategy_comparison": [
            {
                "model": s,
                **{k: c["test"][k] for k in ("pr_auc", "recall", "precision", "brier")},
                "mean_predicted_risk": c["test"]["mean_predicted_risk"],
                "threshold": c["threshold"],
            }
            for s, c in comparison.items()
        ],
        "feature_importance": importance_rows[:10],
        "threshold_sweep": sweep,
        "denial_rate_by": {
            "employer_size": bucket_rates(
                df.employer_size,
                y,
                [0, 10, 50, 250, 1000, 10_000, 2_000_000],
                ["≤10", "11–50", "51–250", "251–1k", "1k–10k", "10k+"],
            ),
            "wage_vs_prevailing": bucket_rates(
                df.wage_vs_prevailing,
                y,
                [50, 100, 105, 120, 150, 400],
                ["Below 100%", "100–105%", "105–120%", "120–150%", "150%+"],
            ),
            "visa_class": [
                {
                    "label": o["label"],
                    "value": round(float(y[df.visa_class == o["value"]].mean()), 4),
                }
                for o in visa_options
                if (df.visa_class == o["value"]).sum() >= 200
            ],
        },
    }
    (REPORTS / "explore.json").write_text(json.dumps(explore, indent=2) + "\n")

    golden = [
        {
            "inputs": s["inputs"],
            "probability": round(float(proba(final, records_to_frame([s["inputs"]]))[0]), 4),
        }
        for s in samples
    ]
    (REPORTS / "golden.json").write_text(json.dumps(golden, indent=2) + "\n")
    for name in ("metrics.json", "explore.json"):
        (artifacts / name).write_text((REPORTS / name).read_text())

    write_figures(comparison, importance_rows, float(y_test.mean()))
    summary = {"final": final_name, "threshold": threshold, "test": comparison[final_name]["test"]}
    print(json.dumps(summary, indent=2))


def write_figures(
    comparison: dict[str, Any], importance: list[dict[str, Any]], base: float
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES.mkdir(parents=True, exist_ok=True)
    names = list(comparison)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    axes[0].bar(names, [comparison[n]["test"]["pr_auc"] for n in names])
    axes[0].set_title("Ranking quality (test PR-AUC)")
    axes[1].bar(names, [comparison[n]["test"]["mean_predicted_risk"] for n in names])
    axes[1].axhline(base, linestyle="--", color="black", label=f"actual denial rate {base:.1%}")
    axes[1].set_title("…but rebalancing inflates predicted risk")
    axes[1].legend()
    for ax in axes:
        ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(FIGURES / "strategy_comparison.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    top = importance[:10][::-1]
    ax.barh([r["label"] for r in top], [r["importance"] for r in top])
    ax.set_xlabel("drop in validation PR-AUC when shuffled (permutation importance)")
    ax.set_title("What drives a PERM denial")
    fig.tight_layout()
    fig.savefig(FIGURES / "feature_importance.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
