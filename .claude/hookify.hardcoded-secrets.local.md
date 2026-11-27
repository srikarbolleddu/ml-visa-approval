---
name: warn-hardcoded-secrets
enabled: true
event: file
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.py$|\.yml$|\.yaml$
  - field: new_text
    operator: regex_match
    pattern: (API_KEY|SECRET|PASSWORD|TOKEN)\s*=\s*["'][A-Za-z0-9_\-]{8,}["']
---

🔐 **Possible hardcoded credential**

Use an environment variable or AWS Secrets Manager/SSM Parameter Store instead of a literal value here.
