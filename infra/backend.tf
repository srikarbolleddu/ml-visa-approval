# Partial backend config — bucket/table are the ONE shared state backend for
# every app scaffolded from these templates. Each app/environment gets its
# own key. See infra/README.md.
#
# terraform init -backend-config=infra/backend.hcl
# (copy infra/backend.hcl.example -> infra/backend.hcl first, gitignored)

terraform {
  backend "s3" {
    encrypt = true
  }
}
