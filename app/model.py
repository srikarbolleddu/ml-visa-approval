"""Load the trained pipeline and explain each prediction with "what-if" contributions."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import skops.io as sio
from sklearn.pipeline import Pipeline

from app.features import FEATURE_ORDER, FIELDS_BY_NAME, NUMERIC_FEATURES, records_to_frame

ARTIFACT_DIR = Path(__file__).parent / "model_artifacts"
MODEL_PATH = ARTIFACT_DIR / "model.skops"
MANIFEST_PATH = ARTIFACT_DIR / "manifest.json"
SAMPLES_PATH = ARTIFACT_DIR / "samples.json"

# skops refuses to load any type not explicitly trusted. These are exactly the non-default types
# this Pipeline(ColumnTransformer + OrdinalEncoder + HistGradientBoostingClassifier) serializes. The
# ColumnTransformer's numeric "passthrough" is stored as functools.partial(check_array, ...); skops
# still checks the wrapped function separately, so trusting `partial` doesn't trust arbitrary code.
# Any other type means the file is not the artifact we trained, so loading fails closed.
TRUSTED_TYPES = frozenset(
    {
        "functools.partial",
        "sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor",
        "sklearn.utils.validation.check_array",
    }
)

# How many inputs to show in an explanation (the largest effects either way).
TOP_CONTRIBUTIONS = 6


def save(pipeline: Pipeline, path: Path = MODEL_PATH) -> None:
    sio.dump(pipeline, path)


def load(path: Path = MODEL_PATH) -> Pipeline:
    untrusted = set(sio.get_untrusted_types(file=path))
    unexpected = untrusted - TRUSTED_TYPES
    if unexpected:
        raise RuntimeError(f"refusing to load model with unexpected types: {sorted(unexpected)}")
    return sio.load(path, trusted=sorted(untrusted))


def _value_text(name: str, value: Any) -> str:
    field = FIELDS_BY_NAME[name]
    if field.kind == "category":
        option = next(o for o in field.to_schema()["options"] if o["value"] == value)
        return f"{field.label.rstrip('?')}: {option['label']}"
    number = float(value)
    if field.unit == "USD":
        text = f"${number:,.0f}"
    elif field.unit == "%":
        text = f"{number:,.0f}%"
    elif field.unit:
        unit = field.unit.removesuffix("s") if number == 1 else field.unit
        text = f"{number:,.0f} {unit}"
    else:
        text = f"{number:.0f}"  # e.g. a year: no thousands separator
    return f"{field.label}: {text}"


class VisaModel:
    def __init__(self, pipeline: Pipeline, manifest: dict[str, Any]) -> None:
        self.pipeline = pipeline
        self.version: str = manifest["model_version"]
        self.denial_threshold: float = manifest["denial_threshold"]
        self.baseline: dict[str, Any] = manifest["baseline"]

    @property
    def threshold(self) -> float:
        """Certification-probability cutoff shown to users (1 - the tuned denial cutoff)."""
        return round(1 - self.denial_threshold, 4)

    def predict(self, record: dict[str, Any]) -> dict[str, Any]:
        """Approval chance plus what-if contributions.

        For each input, re-score the application with just that input set to a typical value
        (training median / most common category). The change in approval chance is that input's
        contribution: positive = this value helps, negative = it hurts. One batched call.
        """
        rows = [record]
        for name in FEATURE_ORDER:
            rows.append({**record, name: self.baseline[name]})
        risks = self.pipeline.predict_proba(records_to_frame(rows))[:, 1]
        risk = float(risks[0])
        approval = 1 - risk

        contributions: list[dict[str, Any]] = []
        for name, risk_without in zip(FEATURE_ORDER, risks[1:], strict=True):
            effect = (float(risk_without) - risk) * 100  # percentage points of approval chance
            if self._is_baseline(name, record[name]) or abs(effect) < 0.05:
                continue
            contributions.append(
                {
                    "label": _value_text(name, record[name]),
                    "field": name,
                    "value": round(effect, 1),
                }
            )
        contributions.sort(key=lambda c: -abs(c["value"]))

        certified = risk < self.denial_threshold
        return {
            "task": "classification",
            "score": round(approval, 4),
            "score_label": "Chance of certification",
            "threshold": self.threshold,
            "positive": certified,
            "outcome": "Likely certified" if certified else "At risk of denial",
            "explanation": {
                "kind": "contributions",
                "title": "What moved the prediction",
                "value_label": (
                    "Change in certification chance (percentage points) compared with a "
                    "typical application"
                ),
                "steps": contributions[:TOP_CONTRIBUTIONS],
            },
            "model_version": self.version,
        }

    def _is_baseline(self, name: str, value: Any) -> bool:
        base = self.baseline[name]
        if name in NUMERIC_FEATURES:
            return float(value) == float(base)
        return value == base


@lru_cache(maxsize=1)
def get_model() -> VisaModel:
    manifest = json.loads(MANIFEST_PATH.read_text())
    return VisaModel(load(MODEL_PATH), manifest)


@lru_cache(maxsize=1)
def get_samples() -> list[dict[str, Any]]:
    return json.loads(SAMPLES_PATH.read_text())
