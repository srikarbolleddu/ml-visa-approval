"""Request/response models. The prediction input is generated from `app.features.FIELDS`, so the
API's validation rules are always exactly the ranges/options the model was trained on."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from app.features import FIELDS


def _field_definition(f: Any) -> tuple[Any, Any]:
    if f.kind == "category":
        annotation: Any = Literal[f.options]  # ty: ignore[invalid-type-form]
        return annotation, Field(description=f.help)
    annotation = float | None if f.optional else float
    default = None if f.optional else ...
    return annotation, Field(default, ge=f.minimum, le=f.maximum, description=f.help)


PredictionInput = create_model(  # ty: ignore[no-matching-overload]
    "PredictionInput",
    __config__=ConfigDict(extra="forbid"),
    **{f.name: _field_definition(f) for f in FIELDS},
)


# The response shape below is the shared ml-demo-kit contract (v1), so one UI renders every
# project's demo. See https://github.com/srikarbolleddu/ml-demo-kit#api-contract.


class ExplanationStep(BaseModel):
    label: str = Field(description="The input and its value, e.g. 'Offered wage: $45,000'.")
    field: str
    value: float = Field(
        description="Change in certification chance (percentage points) vs a typical application."
    )


class Explanation(BaseModel):
    kind: Literal["path", "contributions"]
    title: str
    value_label: str
    steps: list[ExplanationStep]


class PredictionOutput(BaseModel):
    task: Literal["classification", "regression"]
    score: float = Field(description="Chance of certification, 0-1.")
    score_label: str
    threshold: float
    positive: bool
    outcome: str
    explanation: Explanation
    model_version: str


class Sample(BaseModel):
    title: str
    inputs: dict[str, Any]
    actual: str


class SchemaResponse(BaseModel):
    contract: str
    title: str
    description: str
    task: Literal["classification", "regression"]
    target: str
    groups: list[dict[str, str]]
    fields: list[dict[str, Any]]
    model_version: str
    threshold: float
