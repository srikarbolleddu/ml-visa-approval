variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "app_name" {
  type    = string
  default = "ml-visa-approval"
}

variable "environment" {
  type        = string
  description = "dev | staging | prod"
  default     = "dev"
}

variable "image_tag" {
  type        = string
  description = "Lambda container image tag — CI sets this to the git SHA on every push to main."
  default     = "latest"
}

variable "memory_size" {
  type        = number
  description = "MB. 1024 gives the CPU share that keeps pandas/scikit-learn cold starts ~3s."
  default     = 1024
}

variable "timeout" {
  type        = number
  description = "Seconds. A prediction takes ~20ms warm (init is billed separately); this only bounds a stuck request."
  default     = 8
}

variable "throttle_rate_per_second" {
  type        = number
  description = "Steady-state requests/second across ALL callers (API Gateway stage throttle). Concurrency ~= rps x duration, so this keeps the demo to a sliver of the account's shared Lambda pool and caps worst-case abuse cost at a few dollars a month."
  default     = 5
}

variable "throttle_burst" {
  type        = number
  description = "Short burst allowance above the steady rate. Even if every burst request hits a cold start, at most this many Lambdas run at once (3 per stack: three demo stacks can never exceed 9 of the account's 10 concurrent Lambdas, even if all start cold at once)."
  default     = 3
}

variable "cors_allowed_origins" {
  type        = list(string)
  description = "Browser origins allowed to call the demo API: the portfolio + this repo's GitHub Pages."
  default = [
    "https://srikarbolleddu.com",
    "https://www.srikarbolleddu.com",
    "https://srikarbolleddu.github.io",
    "https://d25jb32a4giwex.cloudfront.net", # the portfolio's dev site
    "http://localhost:3000",
    "http://localhost:5173",
  ]
}

variable "github_oidc_provider_arn" {
  type        = string
  description = "ARN of the account's GitHub OIDC provider (created once by the house bootstrap — see infra/README.md)."
}

variable "github_repo" {
  type        = string
  description = "\"owner/repo\" allowed to assume the deploy role via OIDC."
}
