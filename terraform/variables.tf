variable "project_name" {
  type        = string
  default     = "smart-study"
  description = "Project name prefix for resources."
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
  description = "Path to the Lambda deployment zip (app.py at root)."
}

variable "upload_bucket_name" {
  type        = string
  description = "S3 bucket name for uploads."
}

variable "dynamodb_table_name" {
  type        = string
  description = "DynamoDB table name."
}

variable "cors_allowed_origins" {
  type        = list(string)
  description = "Allowed CORS origins for API Gateway and S3."
  default     = ["http://localhost:5173"]
}

variable "text_model_id" {
  type        = string
  description = "Bedrock text model ID."
  default     = "amazon.nova-micro-v1:0"
}

variable "embed_model_id" {
  type        = string
  description = "Bedrock embedding model ID."
  default     = "amazon.titan-embed-text-v1"
}

variable "rag_top_k" {
  type        = number
  description = "Number of top chunks to include in RAG context."
  default     = 3
}
