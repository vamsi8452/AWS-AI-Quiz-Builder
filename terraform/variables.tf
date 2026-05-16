variable "project_name" {
  type        = string
  default     = "smart-study"
  description = "Project name prefix for all resources."
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for all resources."
}

variable "bedrock_region" {
  type        = string
  default     = "us-east-1"
  description = "Bedrock runtime region."
}

variable "lambda_zip_path" {
  type        = string
  description = "Path to the Lambda deployment zip (app.py + agents/ at root)."
}

variable "upload_bucket_name" {
  type        = string
  description = "S3 bucket name for file uploads."
}

variable "dynamodb_table_name" {
  type        = string
  description = "DynamoDB table name."
}

variable "cors_allowed_origins" {
  type        = list(string)
  description = "Allowed CORS origins for API Gateway and S3."
  default = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000"
  ]
}

variable "text_model_id" {
  type        = string
  description = "Bedrock fallback text generation model ID."
  default     = "amazon.nova-pro-v1:0"
}

variable "embed_model_id" {
  type        = string
  description = "Bedrock embedding model ID."
  default     = "amazon.titan-embed-text-v1"
}

variable "coordinator_model_id" {
  type        = string
  description = "Bedrock model ID for the coordinator agent."
  default     = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
}

variable "quiz_gen_model_id" {
  type        = string
  description = "Bedrock model ID for the quiz generation agent."
  default     = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
}

variable "qc_model_id" {
  type        = string
  description = "Bedrock model ID for the QC agent."
  default     = "anthropic.claude-3-haiku-20240307-v1:0"
}

variable "rag_top_k" {
  type        = number
  description = "Number of top RAG chunks to retrieve."
  default     = 3
}

variable "lambda_timeout" {
  type        = number
  description = "Lambda function timeout in seconds."
  default     = 180
}

variable "lambda_memory_size" {
  type        = number
  description = "Lambda function memory in MB."
  default     = 512
}
