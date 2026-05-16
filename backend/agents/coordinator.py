import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
_MODEL_ID = os.getenv(
    "COORDINATOR_MODEL_ID",
    "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
)

from . import qc_agent, quiz_gen_agent

_SYSTEM = (
    "You are a quiz-generation coordinator. Your job is to produce a high-quality "
    "multiple-choice quiz by orchestrating three specialist tools in order:\n\n"
    "1. Call retrieve_relevant_chunks to fetch the most informative content passages.\n"
    "2. Call generate_quiz with that content to produce an initial set of questions.\n"
    "3. Call review_quiz to improve question quality and eliminate weak items.\n"
    "4. Once review_quiz returns, output the final quiz as compact JSON — "
    "no markdown, no extra text:\n"
    '{"quiz":[{"question":"...","choices":["A","B","C","D"],"answerIndex":0,"explanation":"..."}]}'
)

_TOOLS = [
    {
        "name": "retrieve_relevant_chunks",
        "description": (
            "Retrieve the most relevant text chunks from the study material for quiz generation. "
            "Returns a list of content passages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant content (e.g. key topics in the material).",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of chunks to retrieve (default 5).",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "generate_quiz",
        "description": (
            "Generate an initial multiple-choice quiz from the provided content. "
            "Returns a quiz object with 8 questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The study material text to generate questions from.",
                }
            },
            "required": ["content"],
        },
    },
    {
        "name": "review_quiz",
        "description": (
            "Review and improve the quiz for quality, accuracy, and variety. "
            "Returns the improved quiz."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "quiz": {
                    "type": "object",
                    "description": 'The quiz to review, as {"quiz": [...]}.',
                },
                "content": {
                    "type": "string",
                    "description": "The original source content, for grounding checks.",
                },
            },
            "required": ["quiz", "content"],
        },
    },
]

_MAX_ITERATIONS = 8


def _get_client():
    try:
        import boto3
        return boto3.client("bedrock-runtime", region_name=_REGION)
    except Exception:
        return None


def run(
    text: str,
    retrieval_fn: Optional[Callable[[str, int], List[str]]] = None,
) -> Optional[Dict[str, Any]]:
    client = _get_client()
    if client is None:
        logger.warning("boto3 not available — skipping coordinator")
        return None

    messages: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                "Create a high-quality quiz from the following study material. "
                "Use the tools in order: retrieve → generate → review.\n\n"
                f"{text[:4000]}"
            ),
        }
    ]

    for _ in range(_MAX_ITERATIONS):
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 8192,
            "system": _SYSTEM,
            "tools": _TOOLS,
            "messages": messages,
        }
        try:
            response_raw = client.invoke_model(
                modelId=_MODEL_ID,
                body=json.dumps(payload).encode("utf-8"),
                accept="application/json",
                contentType="application/json",
            )
            response = json.loads(response_raw["body"].read())
        except Exception as exc:
            logger.warning("coordinator bedrock call failed: %s", exc)
            return None

        content_blocks = response.get("content", [])
        stop_reason = response.get("stop_reason", "end_turn")

        # Append assistant turn (raw content blocks list)
        messages.append({"role": "assistant", "content": content_blocks})

        if stop_reason != "tool_use":
            for block in content_blocks:
                if block.get("type") == "text":
                    text_out = block["text"].strip()
                    if text_out.startswith("```"):
                        text_out = text_out.split("```")[1]
                        if text_out.startswith("json"):
                            text_out = text_out[4:]
                    try:
                        result = json.loads(text_out)
                        if "quiz" in result and isinstance(result["quiz"], list):
                            return result
                    except (json.JSONDecodeError, ValueError):
                        pass
            return None

        # Execute tool calls and collect results
        tool_results = []
        for block in content_blocks:
            if block.get("type") != "tool_use":
                continue
            tool_name = block["name"]
            tool_input = block["input"]
            tool_use_id = block["id"]
            try:
                result = _dispatch_tool(tool_name, tool_input, text, retrieval_fn)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(result),
                    }
                )
            except Exception as exc:
                logger.warning("tool %s failed: %s", tool_name, exc)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "is_error": True,
                        "content": str(exc),
                    }
                )

        messages.append({"role": "user", "content": tool_results})

    logger.warning("coordinator hit max iterations without finishing")
    return None


def _dispatch_tool(
    name: str,
    inputs: Dict[str, Any],
    fallback_text: str,
    retrieval_fn: Optional[Callable],
) -> Any:
    if name == "retrieve_relevant_chunks":
        query = inputs.get("query", "key concepts")
        top_k = int(inputs.get("top_k", 5))
        if retrieval_fn is not None:
            chunks = retrieval_fn(query, top_k)
            return {"chunks": chunks}
        # Fallback: split raw text into rough chunks
        words = fallback_text.split()
        chunk_size = max(len(words) // top_k, 50)
        chunks = [
            " ".join(words[i : i + chunk_size])
            for i in range(0, len(words), chunk_size)
        ][:top_k]
        return {"chunks": chunks}

    if name == "generate_quiz":
        content = inputs.get("content", fallback_text)
        result = quiz_gen_agent.run(content)
        if result is None:
            raise RuntimeError("quiz_gen_agent returned no result")
        return result

    if name == "review_quiz":
        quiz = inputs.get("quiz")
        content = inputs.get("content", fallback_text)
        result = qc_agent.run(quiz, content)
        # Return original quiz unchanged if QC fails
        return result if result is not None else quiz

    raise ValueError(f"unknown tool: {name}")
