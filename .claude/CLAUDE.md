# ml-visa-approval

US work-visa (PERM labor certification) outcome prediction on public-domain DOL disclosure data,
served as a public demo API, plus a standalone demo UI in `web/`. Rebuilt from a UT Austin PGP-AIML
project (EasyVisa) methodology on open data -- never commit course datasets or notebooks.
Never add nationality / birth country (or obvious proxies) as model inputs.

## Layout
- `app/features.py` -- single source of truth for input fields + cleaning; used by training AND serving.
- `app/model.py` -- skops loading (fails closed on unexpected types), prediction, what-if contributions.
- `app/api/main.py` -- `/schema`, `/samples`, `/explore`, `/predict`; `app/main.py` -- body cap, rate limit, CORS.
- `training/train.py` -- reproducible training; regenerates `app/model_artifacts/` and `reports/`.
- `web/` -- Vite + React demo UI (GitHub Pages).

## Commands
- `uv sync` · `uv run python training/train.py` · `uv run fastapi dev app/main.py`
- Checks: `uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run coverage run -m pytest && uv run coverage report && uv run bandit -q -r app training && uv run pip-audit --skip-editable`
- Lambda image: `docker build -f Dockerfile.lambda -t demo . && docker run -p 9000:8080 demo` then `python3 scripts/smoke_lambda.py http://localhost:9000`

## Rules
- Numbers quoted anywhere (README, portfolio, blog) come from `reports/metrics.json` only.
- Retraining changes the model: commit the regenerated artifacts + reports together; golden tests must pass.
- Public demo: no secrets in code; abuse limits are API Gateway throttling (`infra/`) + body cap + rate limit.
- Infra changes go through the `terraform-aws-deploy` skill and `infra-reviewer` before `apply`.
