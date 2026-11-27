# Work-Visa (PERM) Certification Prediction

Will the US Department of Labor certify this job for a green-card sponsorship? A **gradient-boosting
model** trained on 90,379 real PERM decisions from FY2024, served as a **live demo API** with an
interactive UI. Change the employer, the job offer or the worker's background, and see the chance of
certification plus the inputs that moved it.

- **Live demo:** [srikarbolleddu.github.io/ml-visa-approval](https://srikarbolleddu.github.io/ml-visa-approval/)
  (standalone, from `web/`), also embedded in the
  [case study on srikarbolleddu.com](https://srikarbolleddu.com/projects/visa-approval-prediction)
- **Stack:** scikit-learn (HistGradientBoosting) · imbalanced-learn · FastAPI · AWS Lambda
  (container) · API Gateway · React (Vite)

> Project from the UT Austin Post-Graduate Program in AI & Machine Learning (EasyVisa), rebuilt from
> scratch on public government data. The course's notebooks and data are not used or included.
> A demonstration of the method, not legal advice.

## Results (held-out test set, 18,076 decisions)

Denials are the rare class (5.3%), so the model is scored on finding them.

| | Value |
|---|---|
| Denials caught (recall) | **59%** |
| Flags that were right (precision) | **67%**, vs a 5.3% base rate |
| ROC-AUC / PR-AUC | 0.909 / 0.667 |
| Final model | Gradient boosting trained on the real (unbalanced) data, cutoff tuned on validation |

All numbers come from [`reports/metrics.json`](reports/metrics.json), which `training/train.py` writes.

### SMOTE, undersampling or class weights?

The EasyVisa approach rebalances the training data. I compared four strategies with the same model,
choosing hyperparameters and the decision cutoff on validation data only:

| Strategy | Test PR-AUC | Avg. predicted risk (actual 5.3%) |
|---|---|---|
| **No rebalancing** | **0.667** | 4.7% |
| Class weights | 0.657 | 8.2% |
| SMOTE (SMOTE-NC) | 0.628 | 6.9% |
| Random undersampling | 0.600 | 15.8% |

No rebalancing method beat training on the real data (class weights came closest), and all of them
**distorted the probabilities**: a model trained on rebalanced data believes denials are up to 3×
more common than they are. With a tuned cutoff, the plain model was both the best ranker and the
only one whose probabilities can be read at face value. See
`reports/figures/strategy_comparison.png`.

### What it relies on (and what it doesn't)

Employer size, occupation group, the offered wage and the company's age carry most of the signal.
Employers with 10 or fewer staff are denied 16% of the time; those with over 10,000, 2%.

**The worker's nationality and country of birth are deliberately not inputs.** They are in the
public data, and they would likely improve the score, but a model that predicts a visa outcome from
where someone was born encodes national-origin bias. Some inputs that remain (such as current visa
status) can correlate with nationality; the demo shows their effect openly for every prediction.

## Using the API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/schema` | Input fields with types, ranges, options and help text (drives the demo form) |
| `GET /api/v1/samples` | Six real held-out applications (both outcomes, including mistakes each way) |
| `GET /api/v1/explore` | Chart specs: strategy comparison, calibration, threshold sweep, importance, denial rates |
| `POST /api/v1/predict` | Chance of certification, outcome at the tuned cutoff, and what-if contributions |
| `GET /api/v1/docs` | Interactive OpenAPI docs |

**Explanations:** for each input, the API re-scores the application with that input set to a
typical value (training median or most common category). The change in certification chance is
the input's contribution. It's one batched model call, model-agnostic and easy to read.

Response shapes follow the shared [ml-demo-kit](https://github.com/srikarbolleddu/ml-demo-kit)
contract (`ml-demo-kit/v1`), so the same UI components render every project's demo.

## Run locally

```bash
uv sync
uv run python training/train.py         # downloads the pinned DOL file (sha256-checked) and retrains
uv run fastapi dev app/main.py          # API on http://localhost:8000/api/v1/docs
```

Demo page: `cd web && pnpm install && VITE_DEMO_API_URL=http://localhost:8000/api/v1 pnpm dev`
(leave the variable out to use the recorded responses in `web/src/fixture.json`; refresh them after
retraining with `uv run python scripts/export_web_fixture.py`, which a test enforces).

Checks: `uv run ruff check . && uv run ty check && uv run coverage run -m pytest && uv run coverage report`.
The tests include **golden predictions**: the shipped model must reproduce the outputs recorded at
training time.

## How the notebook became a service

| Notebook step | Where it lives now |
|---|---|
| Load, clean, derive features | `app/features.py` (`clean_raw`): wages annualized, SOC major groups, census regions; unit-tested |
| Feature definitions | `app/features.py` (`FIELDS`), which also drives API validation and the demo form |
| Oversample / undersample, tune, compare | `training/train.py`: fixed seeds, 60/20/20 split, resampling on training data only |
| Model file | `app/model_artifacts/model.skops`. skops loads only allow-listed types, unlike pickle. |
| "Feature importance" cells | Permutation importance in training, plus per-prediction what-if contributions in `app/model.py` |

## Security and abuse limits (public demo)

- No secrets: the API needs none, and nothing visitors send is stored.
- Strict input validation (types, ranges, known categories, no extra fields) and a 4 KB body cap.
- Throttling: an API Gateway stage limit across all callers, plus a per-client rate limit in the app.
- Deploys use GitHub OIDC (no stored AWS keys). The deploy role trusts only this repo's
  approval-gated `production` environment.

## Data and license

- **Dataset:** [US DOL Office of Foreign Labor Certification, PERM Program Disclosure Data, FY2024](https://www.dol.gov/agencies/eta/foreign-labor/performance),
  a US government work in the public domain. Downloaded at training time (checksum-pinned), not
  redistributed. Only job and employer attributes are used, never names, contact details or
  nationality.
- **Code:** see [LICENSE](LICENSE).
