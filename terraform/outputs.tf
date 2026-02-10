output "api_base_url" {
  value       = aws_apigatewayv2_api.http_api.api_endpoint
  description = "Base URL for the HTTP API."
}

output "uploads_bucket" {
  value       = aws_s3_bucket.uploads.bucket
  description = "S3 bucket for uploads."
}

output "dynamodb_table" {
  value       = aws_dynamodb_table.study_sets.name
  description = "DynamoDB table name."
}
