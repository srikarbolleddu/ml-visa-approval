import numpy as np
import pandas as pd
import pytest

from app.features import FEATURE_ORDER, NOT_STATED, TARGET, clean_raw, records_to_frame


def _raw_row(**overrides):
    row = {
        "CASE_STATUS": "Certified",
        "EMPLOYER_NUM_EMPLOYEES": "500",
        "EMP_YEAR_COMMENCED_BUSINESS": "1999",
        "FW_OWNERSHIP_INTEREST": "N",
        "PW_SOC_CODE": "15-1252.00",
        "WAGE_OFFER_FROM": "120000",
        "WAGE_OFFER_UNIT_OF_PAY": "Year",
        "PW_WAGE": "100000",
        "PW_UNIT_OF_PAY": "Year",
        "PW_SKILL_LEVEL": "Level II",
        "MINIMUM_EDUCATION": "Master's",
        "REQUIRED_EXPERIENCE": "Y",
        "REQUIRED_EXPERIENCE_MONTHS": "24",
        "REQUIRED_TRAINING": "N",
        "PROFESSIONAL_OCCUPATION": "Y",
        "WORKSITE_STATE": "CALIFORNIA",
        "FOREIGN_WORKER_EDUCATION": "Master's",
        "CLASS_OF_ADMISSION": "H-1B",
        "FOREIGN_WORKER_CURR_EMPLOYED": "Y",
        "FOREIGN_WORKER_EXP_WITH_EMPL": "N",
    }
    row.update(overrides)
    return row


def test_clean_raw_encodes_target_and_drops_withdrawn():
    df = clean_raw(
        pd.DataFrame(
            [
                _raw_row(),
                _raw_row(CASE_STATUS="Certified-Expired"),
                _raw_row(CASE_STATUS="Denied"),
                _raw_row(CASE_STATUS="Withdrawn"),
            ]
        )
    )

    assert list(df.columns) == [*FEATURE_ORDER, TARGET]
    assert df[TARGET].tolist() == [0, 0, 1]


def test_clean_raw_never_uses_nationality():
    df = clean_raw(
        pd.DataFrame([_raw_row(COUNTRY_OF_CITIZENSHIP="X", FOREIGN_WORKER_BIRTH_COUNTRY="Y")])
    )

    assert not {c for c in df.columns if "country" in c.lower() or "national" in c.lower()}


def test_hourly_wages_are_annualized_and_compared_to_prevailing():
    df = clean_raw(
        pd.DataFrame(
            [_raw_row(WAGE_OFFER_FROM="50", WAGE_OFFER_UNIT_OF_PAY="Hour", PW_WAGE="100000")]
        )
    )

    assert df.loc[0, "annual_wage"] == 50 * 2080
    assert df.loc[0, "wage_vs_prevailing"] == pytest.approx(104.0)


def test_categories_map_to_known_options():
    df = clean_raw(
        pd.DataFrame(
            [
                _raw_row(
                    PW_SOC_CODE="99-0000",
                    WORKSITE_STATE="GUAM",
                    CLASS_OF_ADMISSION="Not in USA",
                    MINIMUM_EDUCATION=np.nan,
                    FOREIGN_WORKER_EXP_WITH_EMPL=np.nan,
                ),
                _raw_row(CLASS_OF_ADMISSION="J-1", WORKSITE_STATE="texas"),
            ]
        )
    )

    assert df.loc[0, "occupation_group"] == "other"
    assert df.loc[0, "region"] == "other"
    assert df.loc[0, "visa_class"] == "not_in_usa"
    assert df.loc[0, "min_education"] == NOT_STATED
    assert df.loc[0, "experience_with_employer"] == NOT_STATED
    assert df.loc[1, "visa_class"] == "other"
    assert df.loc[1, "region"] == "south"


def test_experience_months_is_zero_when_not_required():
    df = clean_raw(
        pd.DataFrame([_raw_row(REQUIRED_EXPERIENCE="N", REQUIRED_EXPERIENCE_MONTHS="36")])
    )

    assert df.loc[0, "experience_months"] == 0


def test_rows_outside_api_ranges_are_dropped():
    df = clean_raw(
        pd.DataFrame(
            [
                _raw_row(),
                _raw_row(WAGE_OFFER_FROM="1"),
                _raw_row(EMP_YEAR_COMMENCED_BUSINESS="1154"),
            ]
        )
    )

    assert len(df) == 1


def test_records_to_frame_matches_training_columns():
    record = clean_raw(pd.DataFrame([_raw_row()])).iloc[0].drop(TARGET).to_dict()

    frame = records_to_frame([record])

    assert list(frame.columns) == FEATURE_ORDER
    assert frame["annual_wage"].dtype == float
