import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
_MODEL_ID = os.getenv(
    "QC_MODEL_ID",
    "anthropic.claude-3-haiku-20240307-v1:0",
)

_SYSTEM = (
    "You are a quiz quality-control reviewer. Given a quiz and its source content, "
    "improve the quiz so every question meets these standards:\n\n"
    "- Questions must be grounded in the source content — remove any that aren't.\n"
    "- No two questions should test the same fact.\n"
    "- Distractors should be plausible but unambiguously wrong.\n"
    "- Explanations should reference the source material.\n"
    "- Preserve the exact JSON structure; keep all 8 questions.\n\n"
    "Output ONLY the improved quiz as compact JSON, no markdown:\n"
    '{"quiz":[{"question":"...","choices":["A","B","C","D"],"answerIndex":0,"explanation":"..."}]}'
)


def _get_client():
    try:
        import boto3
        return boto3.client("bedrock-runtime", region_name=_REGION)
    except Exception:
        return None


def run(quiz: Dict[str, Any], content: str) -> Optional[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        return None

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": _SYSTEM,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Source content:\n\n{content}\n\n"
                    f"Quiz to review:\n\n{json.dumps(quiz)}"
                ),
            }
        ],
    }
    try:
        response = client.invoke_model(
            modelId=_MODEL_ID,
            body=json.dumps(payload).encode("utf-8"),
            accept="application/json",
            contentType="application/json",
        )
        data = json.loads(response["body"].read())
        text = data["content"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text)
        if "quiz" in result and isinstance(result["quiz"], list):
            return result
        return None
    except Exception as exc:
        logger.warning("qc_agent failed: %s", exc)
        return None
