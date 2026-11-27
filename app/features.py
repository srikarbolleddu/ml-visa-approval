"""Feature definitions and cleaning, shared by training (`training/train.py`) and serving (`app/`).

The EasyVisa notebook's data-preparation steps, rebuilt as plain, tested functions over the US
Department of Labor's public PERM disclosure data. Both training and the API import this module, so
the preprocessing a model was trained with can never drift from what a live request gets.

Dataset: US DOL Office of Foreign Labor Certification, PERM Program Disclosure Data, FY2024
(public domain, US government work). https://www.dol.gov/agencies/eta/foreign-labor/performance

Deliberately NOT used:
- Personal and identifying fields (names, addresses, contacts, case numbers).
- The worker's nationality / country of birth: predicting a visa outcome from where someone is
  from would bake national-origin bias into the model (see the README).
- Dates and anything recorded during processing (decision date, audit flags): not known up front.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

TARGET = "denied"
NOT_STATED = "not_stated"


@dataclass(frozen=True)
class Field:
    """One model input. Drives training columns, request validation and the demo form."""

    name: str
    label: str
    kind: Literal["number", "category"]
    group: Literal["employer", "job", "worker"]
    help: str
    source_column: str
    options: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    unit: str | None = None
    optional: bool = False
    option_labels: dict[str, str] = field(default_factory=dict)

    def to_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "group": self.group,
            "help": self.help,
            "optional": self.optional,
        }
        if self.kind == "category":
            schema["options"] = [
                {"value": value, "label": self.option_labels.get(value, _humanize(value))}
                for value in self.options
            ]
        else:
            schema.update(
                {"min": self.minimum, "max": self.maximum, "step": self.step, "unit": self.unit}
            )
        return schema


def _humanize(value: str) -> str:
    return value.replace(".", " ").replace("-", " ").replace("_", " ").strip().capitalize()


_YES_NO = ("Y", "N")
_YES_NO_LABELS = {"Y": "Yes", "N": "No"}
_EDUCATION = (
    "High School",
    "Associate's",
    "Bachelor's",
    "Master's",
    "Doctorate",
    "Other",
    NOT_STATED,
)
_EDUCATION_LABELS = {NOT_STATED: "Not stated"}

SOC_GROUPS = {
    "11": "Management",
    "13": "Business & financial",
    "15": "Computer & mathematical",
    "17": "Architecture & engineering",
    "19": "Life, physical & social science",
    "21": "Community & social service",
    "23": "Legal",
    "25": "Education",
    "27": "Arts, design & media",
    "29": "Healthcare practitioners",
    "31": "Healthcare support",
    "35": "Food preparation & serving",
    "37": "Building & grounds maintenance",
    "39": "Personal care & service",
    "41": "Sales",
    "43": "Office & administrative support",
    "45": "Farming, fishing & forestry",
    "47": "Construction & extraction",
    "49": "Installation, maintenance & repair",
    "51": "Production",
    "53": "Transportation & material moving",
    "other": "Other",
}

REGIONS = {
    "northeast": (
        "CONNECTICUT",
        "MAINE",
        "MASSACHUSETTS",
        "NEW HAMPSHIRE",
        "RHODE ISLAND",
        "VERMONT",
        "NEW JERSEY",
        "NEW YORK",
        "PENNSYLVANIA",
    ),
    "midwest": (
        "ILLINOIS",
        "INDIANA",
        "MICHIGAN",
        "OHIO",
        "WISCONSIN",
        "IOWA",
        "KANSAS",
        "MINNESOTA",
        "MISSOURI",
        "NEBRASKA",
        "NORTH DAKOTA",
        "SOUTH DAKOTA",
    ),
    "south": (
        "DELAWARE",
        "DISTRICT OF COLUMBIA",
        "FLORIDA",
        "GEORGIA",
        "MARYLAND",
        "NORTH CAROLINA",
        "SOUTH CAROLINA",
        "VIRGINIA",
        "WEST VIRGINIA",
        "ALABAMA",
        "KENTUCKY",
        "MISSISSIPPI",
        "TENNESSEE",
        "ARKANSAS",
        "LOUISIANA",
        "OKLAHOMA",
        "TEXAS",
    ),
    "west": (
        "ARIZONA",
        "COLORADO",
        "IDAHO",
        "MONTANA",
        "NEVADA",
        "NEW MEXICO",
        "UTAH",
        "WYOMING",
        "ALASKA",
        "CALIFORNIA",
        "HAWAII",
        "OREGON",
        "WASHINGTON",
    ),
}
_STATE_TO_REGION = {state: region for region, states in REGIONS.items() for state in states}

VISA_CLASSES = ("H-1B", "L-1", "F-1", "TN", "E-2", "B-2", "not_in_usa", "other", NOT_STATED)
_VISA_LABELS = {
    "H-1B": "H-1B (specialty work)",
    "L-1": "L-1 (intra-company transfer)",
    "F-1": "F-1 (student)",
    "TN": "TN (USMCA professional)",
    "E-2": "E-2 (treaty investor)",
    "B-2": "B-2 (visitor)",
    "not_in_usa": "Not in the US",
    "other": "Other",
    NOT_STATED: "Not stated",
}

# Annualize pay so hourly and yearly offers are comparable (2,080 = 52 weeks x 40 hours).
PER_YEAR = {"Year": 1, "Month": 12, "Bi-Weekly": 26, "Week": 52, "Hour": 2080}

FIELDS: tuple[Field, ...] = (
    Field(
        "employer_size",
        "Employees at the company",
        "number",
        "employer",
        "Number of employees the sponsoring employer reported.",
        "EMPLOYER_NUM_EMPLOYEES",
        minimum=0,
        maximum=2_000_000,
        step=1,
        unit="employees",
    ),
    Field(
        "employer_founded",
        "Year the company started",
        "number",
        "employer",
        "Year the employer commenced business.",
        "EMP_YEAR_COMMENCED_BUSINESS",
        minimum=1800,
        maximum=2025,
        step=1,
    ),
    Field(
        "worker_ownership",
        "Worker owns part of the company?",
        "category",
        "employer",
        "Whether the foreign worker has an ownership interest in the employer.",
        "FW_OWNERSHIP_INTEREST",
        options=_YES_NO,
        option_labels=_YES_NO_LABELS,
    ),
    Field(
        "occupation_group",
        "Occupation group",
        "category",
        "job",
        "Standard Occupational Classification (SOC) major group of the job.",
        "PW_SOC_CODE",
        options=tuple(SOC_GROUPS),
        option_labels=SOC_GROUPS,
    ),
    Field(
        "annual_wage",
        "Offered wage (per year)",
        "number",
        "job",
        "The offered wage, converted to a yearly amount.",
        "WAGE_OFFER_FROM",
        minimum=10_000,
        maximum=1_000_000,
        step=1000,
        unit="USD",
    ),
    Field(
        "wage_vs_prevailing",
        "Offered wage vs prevailing wage",
        "number",
        "job",
        "Offered wage as a percentage of the prevailing wage for this job and area.",
        "PW_WAGE",
        minimum=50,
        maximum=400,
        step=1,
        unit="%",
    ),
    Field(
        "wage_level",
        "Prevailing wage level",
        "category",
        "job",
        "DOL skill level of the prevailing wage (I = entry, IV = fully competent).",
        "PW_SKILL_LEVEL",
        options=("Level I", "Level II", "Level III", "Level IV", NOT_STATED),
        option_labels={
            **{level: level for level in ("Level I", "Level II", "Level III", "Level IV")},
            NOT_STATED: "Not stated",
        },
    ),
    Field(
        "min_education",
        "Minimum education required",
        "category",
        "job",
        "Minimum education the job requires.",
        "MINIMUM_EDUCATION",
        options=_EDUCATION,
        option_labels=_EDUCATION_LABELS,
    ),
    Field(
        "experience_months",
        "Experience required",
        "number",
        "job",
        "Months of experience the job requires (0 if none).",
        "REQUIRED_EXPERIENCE_MONTHS",
        minimum=0,
        maximum=240,
        step=1,
        unit="months",
    ),
    Field(
        "training_required",
        "Training required?",
        "category",
        "job",
        "Whether the job requires specific training.",
        "REQUIRED_TRAINING",
        options=_YES_NO,
        option_labels=_YES_NO_LABELS,
    ),
    Field(
        "professional_occupation",
        "Professional occupation?",
        "category",
        "job",
        "Whether the job is a professional occupation.",
        "PROFESSIONAL_OCCUPATION",
        options=_YES_NO,
        option_labels=_YES_NO_LABELS,
    ),
    Field(
        "region",
        "Worksite region",
        "category",
        "job",
        "US Census region of the worksite.",
        "WORKSITE_STATE",
        options=(*REGIONS, "other"),
        option_labels={"other": "Other / territory"},
    ),
    Field(
        "worker_education",
        "Worker's education",
        "category",
        "worker",
        "Highest education the worker has completed.",
        "FOREIGN_WORKER_EDUCATION",
        options=_EDUCATION,
        option_labels=_EDUCATION_LABELS,
    ),
    Field(
        "visa_class",
        "Current visa status",
        "category",
        "worker",
        "The worker's current class of admission to the US.",
        "CLASS_OF_ADMISSION",
        options=VISA_CLASSES,
        option_labels=_VISA_LABELS,
    ),
    Field(
        "currently_employed",
        "Worker currently employed?",
        "category",
        "worker",
        "Whether the worker is currently employed.",
        "FOREIGN_WORKER_CURR_EMPLOYED",
        options=_YES_NO,
        option_labels=_YES_NO_LABELS,
    ),
    Field(
        "experience_with_employer",
        "Gained experience with this employer?",
        "category",
        "worker",
        "Whether the required experience was gained with the sponsoring employer.",
        "FOREIGN_WORKER_EXP_WITH_EMPL",
        options=(*_YES_NO, NOT_STATED),
        option_labels={**_YES_NO_LABELS, NOT_STATED: "Not stated"},
    ),
)

FIELDS_BY_NAME = {f.name: f for f in FIELDS}
NUMERIC_FEATURES = [f.name for f in FIELDS if f.kind == "number"]
CATEGORICAL_FEATURES = [f.name for f in FIELDS if f.kind == "category"]
FEATURE_ORDER = [f.name for f in FIELDS]

CERTIFIED = ("Certified", "Certified-Expired")
DENIED = "Denied"


def _category(series: pd.Series, options: tuple[str, ...], fallback: str) -> pd.Series:
    values = series.astype("string").str.strip()
    return values.where(values.isin(options), fallback).fillna(fallback).astype(str)


def _annualize(amount: pd.Series, unit: pd.Series) -> pd.Series:
    return pd.to_numeric(amount, errors="coerce") * unit.map(PER_YEAR)


def clean_raw(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw PERM disclosure rows → model-ready frame. Withdrawn cases are dropped (no decision)."""
    df = raw[raw["CASE_STATUS"].isin([*CERTIFIED, DENIED])].copy()
    out = pd.DataFrame(index=df.index)
    out["employer_size"] = pd.to_numeric(df["EMPLOYER_NUM_EMPLOYEES"], errors="coerce")
    out["employer_founded"] = pd.to_numeric(df["EMP_YEAR_COMMENCED_BUSINESS"], errors="coerce")
    out["worker_ownership"] = _category(df["FW_OWNERSHIP_INTEREST"], _YES_NO, "N")
    soc = df["PW_SOC_CODE"].astype("string").str[:2]
    out["occupation_group"] = _category(soc, tuple(SOC_GROUPS), "other")
    offered = _annualize(df["WAGE_OFFER_FROM"], df["WAGE_OFFER_UNIT_OF_PAY"])
    prevailing = _annualize(df["PW_WAGE"], df["PW_UNIT_OF_PAY"])
    out["annual_wage"] = offered
    out["wage_vs_prevailing"] = (offered / prevailing * 100).replace([np.inf, -np.inf], np.nan)
    out["wage_level"] = _category(
        df["PW_SKILL_LEVEL"], FIELDS_BY_NAME["wage_level"].options, NOT_STATED
    )
    out["min_education"] = _category(df["MINIMUM_EDUCATION"], _EDUCATION, NOT_STATED)
    experience = pd.to_numeric(df["REQUIRED_EXPERIENCE_MONTHS"], errors="coerce")
    out["experience_months"] = experience.where(df["REQUIRED_EXPERIENCE"] == "Y", 0).fillna(0)
    out["training_required"] = _category(df["REQUIRED_TRAINING"], _YES_NO, "N")
    out["professional_occupation"] = _category(df["PROFESSIONAL_OCCUPATION"], _YES_NO, "N")
    state = df["WORKSITE_STATE"].astype("string").str.strip().str.upper()
    out["region"] = state.map(_STATE_TO_REGION).fillna("other").astype(str)
    out["worker_education"] = _category(df["FOREIGN_WORKER_EDUCATION"], _EDUCATION, NOT_STATED)
    visa = df["CLASS_OF_ADMISSION"].astype("string").str.strip()
    visa = visa.replace({"Not in USA": "not_in_usa"})
    known = visa.isin(VISA_CLASSES)
    out["visa_class"] = visa.where(known | visa.isna(), "other").fillna(NOT_STATED).astype(str)
    out["currently_employed"] = _category(df["FOREIGN_WORKER_CURR_EMPLOYED"], _YES_NO, "N")
    out["experience_with_employer"] = _category(
        df["FOREIGN_WORKER_EXP_WITH_EMPL"], (*_YES_NO, NOT_STATED), NOT_STATED
    )
    out[TARGET] = (df["CASE_STATUS"] == DENIED).astype(int)

    # Drop rows whose core numbers are missing or outside the ranges the API accepts.
    for name in NUMERIC_FEATURES:
        f = FIELDS_BY_NAME[name]
        out = out[out[name].between(f.minimum, f.maximum)]
    return out[[*FEATURE_ORDER, TARGET]].reset_index(drop=True)


def records_to_frame(records: list[dict[str, Any]]) -> pd.DataFrame:
    """API inputs → the same columns `clean_raw` produces (minus the target)."""
    frame = pd.DataFrame(
        [{name: record.get(name) for name in FEATURE_ORDER} for record in records],
        columns=pd.Index(FEATURE_ORDER),
    )
    frame[NUMERIC_FEATURES] = frame[NUMERIC_FEATURES].astype(float)
    return frame
