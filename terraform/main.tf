terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "uploads" {
  bucket = var.upload_bucket_name
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = var.cors_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_dynamodb_table" "study_sets" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }
}

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Scan",
          "dynamodb:Query"
        ]
        Resource = aws_dynamodb_table.study_sets.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.text_model_id}",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.embed_model_id}"
        ]
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name = "${var.project_name}-api"
  role          = aws_iam_role.lambda_role.arn
  handler       = "app.handler"
  runtime       = "python3.11"

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  timeout = 30

  environment {
    variables = {
      STUDY_TABLE_NAME    = aws_dynamodb_table.study_sets.name
      UPLOAD_BUCKET       = aws_s3_bucket.uploads.bucket
      BEDROCK_REGION      = var.bedrock_region
      TITAN_TEXT_MODEL_ID = var.text_model_id
      TITAN_EMBED_MODEL_ID = var.embed_model_id
      RAG_TOP_K           = var.rag_top_k
    }
  }
}

resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-http-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_credentials = false
    allow_headers     = ["content-type"]
    allow_methods     = ["GET", "POST", "OPTIONS"]
    allow_origins     = var.cors_allowed_origins
    max_age           = 3600
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id           = aws_apigatewayv2_api.http_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

locals {
  routes = [
    "POST /study-sets",
    "GET /study-sets",
    "GET /study-sets/{id}",
    "POST /study-sets/{id}/quiz",
    "POST /study-sets/{id}/validate",
    "POST /uploads/presign",
    "POST /study-sets/from-upload"
  ]
}

resource "aws_apigatewayv2_route" "routes" {
  for_each = toset(local.routes)
  api_id   = aws_apigatewayv2_api.http_api.id
  route_key = each.value
  target   = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}
