---
name: require-tests-run
enabled: false
event: stop
action: block
conditions:
  - field: transcript
    operator: not_contains
    pattern: pytest|tests-start.sh
---

**Tests not detected in transcript!**

Before stopping, run `uv run bash scripts/tests-start.sh` to confirm your changes work.

**Note:** disabled by default — flip `enabled: true` once you want strict enforcement on every session.
