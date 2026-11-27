"""Turn the training reports into the ml-demo-kit/v1 `/explore` payload: generic chart specs
(bar, threshold, table) that the shared ExplorePanel renders. Captions pull their numbers from
the reports, so they can never disagree with the charts."""

from __future__ import annotations

from typing import Any


def build_explore(explore: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    test = metrics["test"]
    base_rate = metrics["dataset"]["positive_rate"]
    final = metrics["final_model"]
    strategies = explore["strategy_comparison"]
    rates = explore["denial_rate_by"]
    plain = next(s for s in strategies if s["model"] == "No rebalancing")
    best_ranker = max(strategies, key=lambda s: s["pr_auc"])
    ranking_note = (
        f"Training on the real, unbalanced data ranked denials best (PR-AUC "
        f"{plain['pr_auc']:.3f}); no rebalancing method beat it."
        if best_ranker is plain
        else f"{best_ranker['model']} ranked denials best (PR-AUC {best_ranker['pr_auc']:.3f})."
    )
    size = {r["label"]: r["value"] for r in rates["employer_size"]}
    wage = {r["label"]: r["value"] for r in rates["wage_vs_prevailing"]}
    visa = {r["label"].split(" (")[0]: r["value"] for r in rates["visa_class"]}
    near_minimum = max(wage["Below 100%"], wage["100–105%"], wage["105–120%"])
    most_inflated = max(strategies, key=lambda s: s["mean_predicted_risk"])

    return {
        "contract": "ml-demo-kit/v1",
        "headline": [
            {
                "label": "Denials caught",
                "value": test["recall"],
                "format": "percent",
                "hint": "Recall on held-out applications",
            },
            {
                "label": "Flags that were right",
                "value": test["precision"],
                "format": "percent",
                "hint": f"Precision, vs a {base_rate:.1%} base rate",
            },
            {
                "label": "PR-AUC",
                "value": test["pr_auc"],
                "format": "number",
                "hint": "Ranking quality for denials",
            },
            {
                "label": "Applications",
                "value": metrics["dataset"]["rows"],
                "format": "integer",
                "hint": "DOL PERM decisions, FY2024",
            },
        ],
        "charts": [
            {
                "id": "strategies",
                "kind": "table",
                "title": "SMOTE, undersampling or class weights?",
                "caption": (
                    f"Same model, four ways of handling a {base_rate:.1%} denial rate (held-out "
                    f"test set). {ranking_note} Rebalancing also inflates the model's "
                    "probabilities: it learns that denials are common "
                    f"(average predicted risk {most_inflated['mean_predicted_risk']:.0%} for "
                    f"{most_inflated['model'].lower()} vs {plain['mean_predicted_risk']:.1%} "
                    f"without). Chosen on validation: {final.lower()}."
                ),
                "columns": [
                    {"key": "model", "label": "Strategy"},
                    {"key": "pr_auc", "label": "PR-AUC", "format": "number"},
                    {"key": "recall", "label": "Recall", "format": "percent"},
                    {"key": "precision", "label": "Precision", "format": "percent"},
                    {
                        "key": "mean_predicted_risk",
                        "label": "Avg. predicted risk",
                        "format": "percent",
                    },
                    {"key": "threshold", "label": "Tuned cutoff", "format": "number"},
                ],
                "rows": strategies,
                "highlight": {"key": "model", "value": final},
            },
            {
                "id": "calibration",
                "kind": "bar",
                "title": "Rebalancing distorts probabilities",
                "caption": (
                    "Average predicted denial risk on held-out applications, against the real "
                    "denial rate. Only the unbalanced model's probabilities can be read as real "
                    "chances; the others need their own tuned cutoff."
                ),
                "format": "percent",
                "reference": {"value": base_rate, "label": "Actual denial rate"},
                "items": [
                    {"label": s["model"], "value": s["mean_predicted_risk"]} for s in strategies
                ],
            },
            {
                "id": "threshold",
                "kind": "threshold",
                "title": "Flagging applications for review",
                "caption": (
                    "Applications with denial risk above the cutoff are flagged. Lower it to catch "
                    "more denials, at the cost of flagging more applications that would have been "
                    "certified."
                ),
                "positive_label": "Denied",
                "negative_label": "Certified",
                "selected": metrics["threshold"],
                "sweep": explore["threshold_sweep"],
            },
            {
                "id": "importance",
                "kind": "bar",
                "title": "What the model relies on",
                "caption": (
                    "How much ranking quality drops when each input is shuffled (permutation "
                    "importance on validation data). Nationality is deliberately not an input."
                ),
                "format": "number",
                "items": [
                    {"label": f["label"], "value": f["importance"]}
                    for f in explore["feature_importance"]
                    if f["importance"] > 0
                ],
            },
            {
                "id": "rate-size",
                "kind": "bar",
                "title": "Denial rate by employer size",
                "caption": (
                    f"Employers with 10 or fewer staff are denied {size['≤10']:.0%} of the time; "
                    f"those with over 10,000 only {size['10k+']:.0%}."
                ),
                "format": "percent",
                "reference": {"value": base_rate, "label": "Overall"},
                "items": rates["employer_size"],
            },
            {
                "id": "rate-wage",
                "kind": "bar",
                "title": "Denial rate by offered wage vs prevailing wage",
                "caption": (
                    f"Offers at 150%+ of the prevailing wage are denied {wage['150%+']:.1%} of "
                    f"the time; offers within 20% of it, up to {near_minimum:.1%}."
                ),
                "format": "percent",
                "reference": {"value": base_rate, "label": "Overall"},
                "items": rates["wage_vs_prevailing"],
            },
            {
                "id": "rate-visa",
                "kind": "bar",
                "title": "Denial rate by the worker's current visa",
                "caption": (
                    f"Workers already on an H-1B ({visa['H-1B']:.1%}) or L-1 "
                    f"({visa['L-1']:.1%}) are rarely denied; visitors on a B-2 much more often "
                    f"({visa['B-2']:.0%})."
                ),
                "format": "percent",
                "reference": {"value": base_rate, "label": "Overall"},
                "items": rates["visa_class"],
            },
        ],
    }
