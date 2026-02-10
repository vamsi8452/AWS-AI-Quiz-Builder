# Smart Study Backend (Summary-Only)

This Lambda handler implements the quiz-only API used by the frontend.
It supports API Gateway HTTP API (v2) event payloads and can run with a DynamoDB
table or fall back to in-memory storage for local testing.

## Endpoints

- `POST /study-sets` → create a study set
  - body: `{ "text": "...", "title": "optional" }`
- `POST /uploads/presign` → get a presigned S3 upload URL
  - body: `{ "filename": "notes.txt" }`
- `POST /study-sets/from-upload` → create a study set from an uploaded file
  - body: `{ "key": "uploads/uuid_notes.txt", "title": "optional" }`
- `GET /study-sets` → list study sets
- `GET /study-sets/{id}` → fetch a study set
- `POST /study-sets/{id}/quiz` → generate (or return cached) quiz
- `POST /study-sets/{id}/validate` → validate answers for a quiz

## DynamoDB (optional)

Set `STUDY_TABLE_NAME` to enable DynamoDB persistence. Table schema:

- Partition key: `PK` (string)
- Sort key: `SK` (string)

Stored items:

- Study set: `PK={id}`, `SK=STUDY`, plus study set fields
- Text: `PK={id}`, `SK=TEXT`, `text`
- Summary: `PK={id}`, `SK=SUMMARY`, `text`, `updatedAt`

If `STUDY_TABLE_NAME` is unset, the handler uses in-memory storage (non-persistent).

## S3 uploads (Phase 3)

Set `UPLOAD_BUCKET` to enable presigned uploads. The flow is:

1. Call `POST /uploads/presign` with `filename`
2. Upload to the returned `url` via HTTP PUT (content-type `text/plain`)
3. Call `POST /study-sets/from-upload` with the returned `key`

## Local testing (example)

```bash
python -m venv .venv
source .venv/bin/activate
pip install boto3
```

Use any local Lambda runner or API Gateway emulator. The handler is:

- `backend/app.py` → `handler`

Example request payload (HTTP API v2):

```json
{
  "version": "2.0",
  "rawPath": "/study-sets",
  "requestContext": { "http": { "method": "POST" } },
  "body": "{\"text\":\"hello world\"}",
  "isBase64Encoded": false
}
```
