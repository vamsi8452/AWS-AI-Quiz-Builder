# Terraform Stack (Smart Study)

This stack provisions:
- Lambda (Python 3.11) for the API
- HTTP API Gateway (CORS enabled)
- DynamoDB table (`pk`/`sk`)
- S3 uploads bucket with CORS and public access blocked
- IAM role and policies for Lambda (DynamoDB, S3, Bedrock, CloudWatch)

## Prereqs

- Terraform >= 1.5
- AWS credentials configured
- Lambda deployment zip (with `app.py` at the root)

## Deploy

```bash
cd terraform
terraform init
terraform apply \
  -var="lambda_zip_path=../lambda.zip" \
  -var="upload_bucket_name=your-upload-bucket-name" \
  -var="dynamodb_table_name=smartstudy"
```

## Notes

- Default CORS allows `http://localhost:5173`. Override via `cors_allowed_origins`.
- Bedrock model IDs default to Nova Micro (text) + Titan embeddings. Override via vars if needed.
- Make sure `lambda.zip` includes any third-party deps (e.g., PyPDF2).
