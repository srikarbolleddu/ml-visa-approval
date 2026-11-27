# infra/ — Terraform → AWS (Lambda)

Deploys as a **container-image Lambda function** behind an **API Gateway HTTP API** with stage throttling: the hard abuse ceiling for this public demo. The account's Lambda concurrency pool is small (10) and shared with other services, so reserved concurrency isn't available; the gateway's burst limit caps simultaneous cold starts. With three demo stacks at burst 3 the worst case briefly nearly fills the pool, so don't add stacks or raise bursts until the account's concurrency quota is increased. Region **us-east-2**; Terraform state lives in the shared house backend (us-east-1).

## One-time account setup (do this once, not per app)

Every app scaffolded from any of the house templates shares **one** Terraform state backend and **one** GitHub OIDC provider.

1. **Remote state backend** (S3 bucket + DynamoDB lock table):
   ```bash
   aws s3api create-bucket --bucket <your-house-terraform-state> --region us-east-1
   aws s3api put-bucket-versioning --bucket <your-house-terraform-state> --versioning-configuration Status=Enabled
   aws dynamodb create-table --table-name <your-house-terraform-locks> \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST
   ```
2. **GitHub OIDC provider**:
   ```bash
   aws iam create-open-id-connect-provider \
     --url https://token.actions.githubusercontent.com \
     --client-id-list sts.amazonaws.com \
     --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
   ```
   Save the ARN — every app's `terraform.tfvars` needs it.

Skip this section entirely if you already did it for another app built from these templates — reuse the same bucket/table/provider.

## Per-app setup

1. Copy `infra/backend.hcl.example` → `infra/backend.hcl` (gitignored) and fill in the shared bucket/table.
2. Copy `infra/environments/prod.tfvars.example` → `infra/environments/prod.tfvars` and fill in `github_oidc_provider_arn` + `github_repo`.
3. Build and push the **first** image manually (Terraform can't create a Lambda function pointing at a tag that doesn't exist yet in ECR):
   ```bash
   cd infra && terraform init -backend-config=backend.hcl
   terraform apply -target=aws_ecr_repository.app -var-file=environments/prod.tfvars
   cd ..
   aws ecr get-login-password | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-2.amazonaws.com
   # Tag must equal image_tag in prod.tfvars ("bootstrap"); tags are immutable.
   # --provenance=false: Lambda rejects the OCI image index a provenance attestation creates.
   docker build --provenance=false --platform linux/amd64 -f Dockerfile.lambda -t <ecr-repo-url>:bootstrap .
   docker push <ecr-repo-url>:bootstrap
   ```
4. Then the full apply: `terraform apply -var-file=environments/prod.tfvars`.
5. Put the `deploy_role_arn` output into the repo's GitHub Actions repo variables (e.g. `AWS_DEPLOY_ROLE_ARN`) so CI can assume it — see `.github/workflows/deploy.yml`.

## Public-demo safeguards in place

- **Throttling:** API Gateway stage limits (`throttle_rate_per_second`, `throttle_burst`) apply across all callers. The app adds a body-size cap and a per-client rate limit.
- **CORS:** restricted to `cors_allowed_origins` (the portfolio + GitHub Pages). This is a browser courtesy, not access control.
- **Deploys:** the deploy role trusts only `repo:<owner>/<repo>:environment:production`. Add a required reviewer to that GitHub environment so every deploy needs approval.
- **Runtime role:** CloudWatch Logs only. The model ships inside the image, so the function needs no other AWS access.
- Have `infra-reviewer` look at any Terraform diff before `terraform apply`.
