locals {
  name = "${var.app_name}-${var.environment}"
}

# --- Container registry ---

resource "aws_ecr_repository" "app" {
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.environment != "prod"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the live image plus two rollbacks (storage is the demo's main cost)"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 3
      }
      action = { type = "expire" }
    }]
  })
}

# --- Logs ---

resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 14 # a public demo: short retention keeps log storage near zero
}

# --- Lambda execution role ---
# Task-specific AWS permissions go here as named, least-privilege
# statements — never a wildcard. Empty by design until the app needs one
# (e.g. Secrets Manager read for a specific secret ARN).

resource "aws_iam_role" "lambda_exec" {
  name = "${local.name}-lambda-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_logs" {
  name = "${local.name}-logs"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${aws_cloudwatch_log_group.app.arn}:*"
    }]
  })
}

# --- Lambda function (container image), built from Dockerfile.lambda ---

resource "aws_lambda_function" "app" {
  function_name = local.name
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  memory_size   = var.memory_size
  timeout       = var.timeout

  environment {
    variables = {
      # pydantic-settings parses list values from JSON.
      ALLOWED_ORIGINS = jsonencode(var.cors_allowed_origins)
    }
  }

  depends_on = [aws_cloudwatch_log_group.app]

  # After the first apply, the Deploy workflow owns the image (it pushes git-SHA tags and calls
  # update-function-code). Without this, a later `terraform apply` would roll the code back.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

# --- Public HTTPS endpoint: API Gateway HTTP API (not a raw Function URL) ---
# The gateway's stage throttling is the hard abuse ceiling for this public demo. Reserved
# concurrency can't be used: this account's Lambda concurrency limit is 10, all of which must stay
# unreserved -- and that pool is shared with the portfolio's own services, so the demo must never
# be able to saturate it.

resource "aws_apigatewayv2_api" "http" {
  name          = local.name
  protocol_type = "HTTP"

  # A browser courtesy, not access control: the throttling below is what limits callers.
  cors_configuration {
    allow_headers = ["content-type"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_origins = var.cors_allowed_origins
    max_age       = 600
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.app.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = var.timeout * 1000
}

# Catch-all route: FastAPI does the real method/path dispatch and validation.
resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = var.throttle_rate_per_second
    throttling_burst_limit = var.throttle_burst
  }
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
