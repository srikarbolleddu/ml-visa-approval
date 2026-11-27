---
name: warn-sensitive-files
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.env$|\.env\.|credentials|secrets|backend\.hcl$|\.tfvars$
---

🔐 **Sensitive file detected**

You're editing a file that may contain credentials or infra secrets:
- Ensure nothing is hardcoded — use env vars / AWS Secrets Manager / SSM
- Verify this file is in `.gitignore`
- Never commit real AWS account IDs, ARNs with account numbers, or DB passwords
