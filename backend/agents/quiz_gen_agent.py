import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
_MODEL_ID = os.getenv(
    "QUIZ_GEN_MODEL_ID",
    "us.anthropic.claude-3-5-haiku-20241022-v1:0",
)

_SYSTEM = (
    "You are a quiz-generation specialist. Given source content, produce exactly 8 "
    "multiple-choice questions that test genuine comprehension.\n\n"
    "Rules:\n"
    "- Each question must have exactly 4 answer choices.\n"
    "- answerIndex is 0-based (0–3).\n"
    "- Distribute correct answers across all four positions.\n"
    "- Questions must be specific to the content — no generic trivia.\n"
    "- Distractors must be plausible but clearly wrong to someone who read the material.\n"
    "- Include a one-sentence explanation for the correct answer.\n\n"
    "Output ONLY compact JSON, no markdown:\n"
    '{"quiz":[{"question":"...","choices":["A","B","C","D"],"answerIndex":0,"explanation":"..."}]}'
)


def _get_client():
    try:
        import boto3
        return boto3.client("bedrock-runtime", region_name=_REGION)
    except Exception:
        return None


def run(content: str) -> Optional[Dict[str, Any]]:
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
                "content": f"Generate a quiz for the following content:\n\n{content}",
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
        logger.warning("quiz_gen_agent failed: %s", exc)
        return None
