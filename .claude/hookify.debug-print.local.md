---
name: warn-debug-print
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: ^app/.*\.py$
  - field: new_text
    operator: regex_match
    pattern: print\(
---

🔍 **`print()` detected in application code**

Ruff's `T201` rule (already enabled in `pyproject.toml`) will flag this too. Consider proper logging instead if this isn't temporary debugging.
