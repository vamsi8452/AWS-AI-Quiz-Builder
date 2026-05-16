project_name        = "smart-study"
aws_region          = "us-east-1"
bedrock_region      = "us-east-1"
lambda_zip_path     = "/tmp/lambda.zip"
upload_bucket_name  = "rag8452"
dynamodb_table_name = "smartstudy"
lambda_timeout      = 180
lambda_memory_size  = 512

cors_allowed_origins = [
  "https://d5l03r9aay7es.cloudfront.net",
  "http://localhost:5173",
  "http://localhost:5174",
  "http://localhost:3000"
]

text_model_id        = "amazon.nova-pro-v1:0"
embed_model_id       = "amazon.titan-embed-text-v1"
coordinator_model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
quiz_gen_model_id    = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
qc_model_id          = "us.anthropic.claude-3-5-haiku-20241022-v1:0"
rag_top_k            = 3
