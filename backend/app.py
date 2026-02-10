import hashlib
import json
import os
import random
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import boto3
    from boto3.dynamodb.conditions import Attr, Key
except Exception:  # pragma: no cover - boto3 available in Lambda
    boto3 = None
    Attr = None
    Key = None

try:
    from PyPDF2 import PdfReader
except Exception:  # pragma: no cover - optional dependency
    PdfReader = None


STUDY_TABLE_NAME = os.getenv("STUDY_TABLE_NAME", "").strip()
UPLOAD_BUCKET = os.getenv("UPLOAD_BUCKET", "").strip()
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1").strip()
TITAN_TEXT_MODEL_ID = os.getenv("TITAN_TEXT_MODEL_ID", "amazon.nova-pro-v1:0").strip()
TITAN_EMBED_MODEL_ID = os.getenv("TITAN_EMBED_MODEL_ID", "amazon.titan-embed-text-v1").strip()
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
ALLOWED_CONTENT_TYPES = {"text/plain", "application/pdf", "application/octet-stream"}
DEBUG_MODEL_OUTPUT = os.getenv("DEBUG_MODEL_OUTPUT", "").lower() in {"1", "true", "yes"}
USE_MOCK_QUIZ = os.getenv("USE_MOCK_QUIZ", "").lower() in {"1", "true", "yes"}
ALLOW_FALLBACK = os.getenv("ALLOW_FALLBACK", "true").lower() in {"1", "true", "yes"}

_memory_store = {
    "study_sets": {},
    "texts": {},
    "chunks": {},
    "quizzes": {},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json_response(status: int, payload: Any) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET,POST,OPTIONS",
            "access-control-allow-headers": "content-type",
        },
        "body": json.dumps(payload, default=_json_serialize),
    }


def _get_table():
    if not STUDY_TABLE_NAME or boto3 is None:
        return None
    return boto3.resource("dynamodb").Table(STUDY_TABLE_NAME)


def _get_s3_client():
    if not UPLOAD_BUCKET or boto3 is None:
        return None
    return boto3.client("s3")


def _get_bedrock_client():
    if boto3 is None:
        return None
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)


def _extract_words(text: str) -> List[str]:
    return [w for w in __import__("re").findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3]


def _normalize_content_type(filename: str, content_type: str) -> str:
    if content_type in ALLOWED_CONTENT_TYPES:
        return content_type
    if filename.lower().endswith(".pdf"):
        return "application/pdf"
    return "text/plain"


def _extract_text_from_pdf(data: bytes) -> Optional[str]:
    if PdfReader is None:
        return None
    try:
        import io

        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text:
                parts.append(page_text)
        text = "\n".join(parts).strip()
        return text if text else None
    except Exception:
        return None


def _extract_text_from_upload(
    data: bytes, content_type: str, filename: str
) -> Tuple[Optional[str], Optional[str]]:
    normalized = _normalize_content_type(filename, content_type)
    if normalized in {"application/pdf", "application/octet-stream"} and filename.lower().endswith(".pdf"):
        text = _extract_text_from_pdf(data)
        if not text:
            return None, "Unable to extract text from PDF. Ensure PyPDF2 is packaged."
        return text, None
    try:
        return data.decode("utf-8"), None
    except Exception:
        return data.decode("utf-8", errors="replace"), None


def _chunk_text(text: str, max_words: int = 180) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    for idx in range(0, len(words), max_words):
        chunk = " ".join(words[idx : idx + max_words]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks


def _invoke_bedrock_json(client, model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(payload).encode("utf-8"),
        accept="application/json",
        contentType="application/json",
    )
    body = response.get("body")
    if hasattr(body, "read"):
        body = body.read()
    return json.loads(body)


def _is_nova_text_model() -> bool:
    return TITAN_TEXT_MODEL_ID.startswith("amazon.nova")


def _invoke_text_model(client, prompt: str) -> Optional[str]:
    if _is_nova_text_model():
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            "inferenceConfig": {
                "maxTokens": 1200,
                "temperature": 0.2,
                "topP": 0.9,
            },
        }
        data = _invoke_bedrock_json(client, TITAN_TEXT_MODEL_ID, payload)
        output = data.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "").strip()
        return None
    payload = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 1200,
            "temperature": 0.2,
            "topP": 0.9,
        },
    }
    data = _invoke_bedrock_json(client, TITAN_TEXT_MODEL_ID, payload)
    results = data.get("results", [])
    if results:
        return results[0].get("outputText", "").strip()
    return None


def _embed_text(client, text: str) -> Optional[List[float]]:
    try:
        data = _invoke_bedrock_json(client, TITAN_EMBED_MODEL_ID, {"inputText": text})
        return data.get("embedding")
    except Exception:
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    vec_a = [float(x) for x in a]
    vec_b = [float(x) for x in b]
    dot = sum(x * y for x, y in zip(vec_a, vec_b))
    norm_a = sum(x * x for x in vec_a) ** 0.5
    norm_b = sum(y * y for y in vec_b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _to_decimal_list(values: List[float]) -> List[Decimal]:
    return [Decimal(str(v)) for v in values]


def _store_chunks(table, study_id: str, text: str) -> None:
    chunks = _chunk_text(text)
    if not chunks:
        return
    client = _get_bedrock_client()
    if client is None:
        return

    stored_chunks = []
    for idx, chunk in enumerate(chunks):
        embedding = _embed_text(client, chunk)
        if not embedding:
            continue
        stored_chunks.append({"text": chunk, "embedding": embedding})

        if table is None:
            continue
        embedding_decimal = _to_decimal_list(embedding)
        table.put_item(
            Item={
                "pk": study_id,
                "sk": f"CHUNK#{idx:03d}",
                "text": chunk,
                "embedding": embedding_decimal,
            }
        )

    if table is None:
        _memory_store["chunks"][study_id] = stored_chunks


def _fetch_chunks(table, study_id: str) -> List[Dict[str, Any]]:
    if table is None:
        return _memory_store["chunks"].get(study_id, [])

    if Key:
        response = table.query(
            KeyConditionExpression=Key("pk").eq(study_id) & Key("sk").begins_with("CHUNK#")
        )
        return response.get("Items", [])

    response = table.scan(FilterExpression=Attr("pk").eq(study_id))
    items = response.get("Items", [])
    return [item for item in items if str(item.get("sk", "")).startswith("CHUNK#")]


def _normalize_embedding(values: List[Any]) -> List[float]:
    return [float(value) for value in values] if values else []


def _select_chunks_for_quiz(
    table, study_id: str, text: str, top_k: int
) -> List[str]:
    if top_k <= 0:
        return []
    chunks = _fetch_chunks(table, study_id)
    if not chunks:
        return []

    client = _get_bedrock_client()
    if client is None:
        return [chunk.get("text", "") for chunk in chunks[:top_k] if chunk.get("text")]

    query_text = " ".join(text.split()[:300]).strip()
    if not query_text:
        return [chunk.get("text", "") for chunk in chunks[:top_k] if chunk.get("text")]

    query_embedding = _embed_text(client, query_text)
    if not query_embedding:
        return [chunk.get("text", "") for chunk in chunks[:top_k] if chunk.get("text")]

    scored: List[Tuple[float, str]] = []
    for chunk in chunks:
        embedding = _normalize_embedding(chunk.get("embedding") or [])
        if not embedding:
            continue
        score = _cosine_similarity(query_embedding, embedding)
        scored.append((score, chunk.get("text", "")))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk_text for _, chunk_text in scored if chunk_text][:top_k]
    if selected:
        return selected
    return [chunk.get("text", "") for chunk in chunks[:top_k] if chunk.get("text")]


def _parse_quiz_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(text)
        quiz = data.get("quiz")
        if not isinstance(quiz, list) or not quiz:
            return None
        return data
    except Exception:
        return None


def _extract_json_block(text: str) -> Optional[str]:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return stripped[start : end + 1]

def _seeded_random(seed_text: str) -> random.Random:
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    seed = int(digest[:8], 16)
    return random.Random(seed)


def _build_fallback_quiz(text: str) -> Dict[str, Any]:
    words = _extract_words(text)
    if not words:
        words = ["concept", "topic", "term", "detail"]
    counts: Dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    ordered = [w for w, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
    top_terms = ordered[:5] if ordered else ["concept"]
    distractors = ordered[1:] if len(ordered) > 1 else ["topic", "term", "detail"]
    fallback_fillers = ["topic", "term", "detail", "example", "principle", "element"]
    not_in_text = [w for w in fallback_fillers if w not in counts]

    quiz = []
    question_count = min(5, len(top_terms)) if top_terms else 3
    for idx in range(question_count):
        rng = _seeded_random(f"{text}-{idx}")

        if idx == 0 and len(top_terms) >= 2:
            correct = top_terms[0]
            pool = [w for w in ordered[1:] if w != correct]
            if len(pool) < 3:
                pool.extend([w for w in fallback_fillers if w != correct])
            pool = list(dict.fromkeys(pool))
            if len(pool) < 3:
                pool.extend(["item", "idea", "concept"])
            choices = [correct] + rng.sample(pool, k=3)
            rng.shuffle(choices)
            quiz.append(
                {
                    "question": "Which term appears most frequently in the study text?",
                    "choices": choices,
                    "answerIndex": choices.index(correct),
                    "explanation": f"'{correct}' appears more often than the other options.",
                }
            )
            continue

        if idx % 2 == 1 and not_in_text:
            correct = not_in_text[idx % len(not_in_text)]
            pool = [w for w in ordered if w != correct]
            if len(pool) < 3:
                pool.extend([w for w in fallback_fillers if w != correct])
            pool = list(dict.fromkeys(pool))
            choices = [correct] + rng.sample(pool, k=3)
            rng.shuffle(choices)
            quiz.append(
                {
                    "question": "Which term does NOT appear in the study text?",
                    "choices": choices,
                    "answerIndex": choices.index(correct),
                    "explanation": f"'{correct}' is not present in the provided content.",
                }
            )
            continue

        term = top_terms[idx % len(top_terms)]
        pool = [w for w in distractors if w != term]
        if len(pool) < 3:
            pool.extend([w for w in fallback_fillers if w != term])
        pool = list(dict.fromkeys(pool))
        if len(pool) < 3:
            pool.extend(["item", "idea", "concept"])
        choices = [term] + rng.sample(pool, k=3)
        rng.shuffle(choices)
        quiz.append(
            {
                "question": "Which term appears in the study text?",
                "choices": choices,
                "answerIndex": choices.index(term),
                "explanation": f"'{term}' is present in the provided content.",
            }
        )
    return {"quiz": quiz, "_fallback": True}


def _quality_filter_quiz(
    client, quiz: Dict[str, Any], content: str
) -> Optional[Dict[str, Any]]:
    prompt = (
        "You are QuizQC. Improve the quiz quality using only the CONTENT.\n"
        "Fix vague questions, weak distractors, or incorrect answers.\n"
        "Rules:\n"
        "- Use only the CONTENT.\n"
        "- Keep 8-12 questions.\n"
        "- 4 choices per question, one correct.\n"
        "- Remove any \"term appears/does not appear/frequency\" questions.\n"
        "- Ensure variety: definition, cause/effect, application, inference, compare/contrast.\n"
        "- Avoid \"All of the above\" and \"None of the above\".\n"
        "- Explanations must be grounded in the content.\n\n"
        "Return strict JSON only (same schema), no markdown:\n"
        "{\n"
        '  "quiz": [\n'
        '    {"question":"...","choices":["...","...","...","..."],'
        '"answerIndex":0,"explanation":"..."}\n'
        "  ]\n"
        "}\n\n"
        f"CONTENT:\n{content}\n\n"
        f"QUIZ:\n{json.dumps(quiz)}"
    )
    output = _invoke_text_model(client, prompt)
    if not output:
        return None
    parsed = _parse_quiz_json(output)
    if parsed:
        return parsed
    extracted = _extract_json_block(output)
    if extracted:
        return _parse_quiz_json(extracted)
    return None


def _generate_quiz_with_llm(table, study_id: str, text: str) -> Optional[Dict[str, Any]]:
    if USE_MOCK_QUIZ:
        return _build_fallback_quiz(text)
    client = _get_bedrock_client()
    if client is None:
        return _build_fallback_quiz(text) if ALLOW_FALLBACK else None
    chunks = _select_chunks_for_quiz(table, study_id, text, RAG_TOP_K)
    if chunks:
        content = "\n\n".join(
            f"[Chunk {idx + 1}]\n{chunk}" for idx, chunk in enumerate(chunks)
        )
    else:
        content = text[:6000]

    def _build_prompt(prompt_content: str, strict: bool) -> str:
        question_rule = "- 8 questions exactly.\n" if strict else "- 8-12 questions.\n"
        explanation_rule = (
            "- Explanations must be 1 short sentence.\n" if strict else "- Explanations must cite the content (paraphrase is fine).\n"
        )
        return (
            "You are QuizGen. Create a high-quality multiple-choice quiz from the CONTENT.\n"
            "Target: adult learners; focus on concepts, application, and reasoning.\n"
            "Rules:\n"
            "- Use only the CONTENT. Do not add outside facts.\n"
            f"{question_rule}"
            "- 4 choices per question, one correct.\n"
            "- Each question must be specific and non-trivial.\n"
            "- Do NOT ask about word presence, term frequency, spelling, or formatting.\n"
            "- Avoid \"All of the above\" and \"None of the above\".\n"
            "- Mix question types: definition, cause/effect, application, inference, compare/contrast.\n"
            "- Choices should be similar length and plausible; only one clearly correct.\n"
            f"{explanation_rule}\n"
            "Return compact JSON only, no markdown, no code fences:\n"
            "{\"quiz\":[{\"question\":\"...\",\"choices\":[\"...\",\"...\",\"...\",\"...\"],"
            "\"answerIndex\":0,\"explanation\":\"...\"}]}\n\n"
            f"CONTENT:\n{prompt_content}"
        )

    attempts = [
        (content, False),
        (content[:3000], True),
    ]

    for prompt_content, strict in attempts:
        prompt = _build_prompt(prompt_content, strict)
        try:
            output = _invoke_text_model(client, prompt)
        except Exception as exc:
            if DEBUG_MODEL_OUTPUT:
                return {"_error": str(exc)}
            return _build_fallback_quiz(text) if ALLOW_FALLBACK else None
        if not output:
            continue
        parsed = _parse_quiz_json(output)
        if parsed:
            filtered = _quality_filter_quiz(client, parsed, prompt_content)
            return filtered or parsed
        extracted = _extract_json_block(output)
        if extracted:
            extracted_parsed = _parse_quiz_json(extracted)
            if extracted_parsed:
                filtered = _quality_filter_quiz(client, extracted_parsed, prompt_content)
                return filtered or extracted_parsed
    if ALLOW_FALLBACK:
        fallback = _build_fallback_quiz(text)
        if DEBUG_MODEL_OUTPUT:
            fallback["_raw"] = output if "output" in locals() else ""
        return fallback
    if DEBUG_MODEL_OUTPUT:
        return {"_raw": output if "output" in locals() else ""}
    return None


def _normalize_answers(answers: List[Any], total: int) -> List[Optional[int]]:
    normalized: List[Optional[int]] = []
    for idx in range(total):
        if idx < len(answers) and isinstance(answers[idx], int):
            normalized.append(answers[idx])
        else:
            normalized.append(None)
    return normalized

def _create_study_set(
    title: Optional[str], text: str, source_type: str = "text"
) -> Dict[str, Any]:
    study_id = str(uuid.uuid4())
    created_at = _now_iso()
    study_set = {
        "id": study_id,
        "title": title.strip() if title else "AI Quiz Builder",
        "createdAt": created_at,
        "status": "READY",
        "sourceType": source_type,
    }
    return study_set


def _put_study_set(table, study_set: Dict[str, Any], text: str) -> None:
    if table is None:
        _memory_store["study_sets"][study_set["id"]] = study_set
        _memory_store["texts"][study_set["id"]] = text
        return

    table.put_item(
        Item={
            "pk": study_set["id"],
            "sk": "STUDY",
            **study_set,
        }
    )
    table.put_item(
        Item={
            "pk": study_set["id"],
            "sk": "TEXT",
            "text": text,
        }
    )


def _list_study_sets(table) -> List[Dict[str, Any]]:
    if table is None:
        items = list(_memory_store["study_sets"].values())
        return sorted(items, key=lambda item: item["createdAt"], reverse=True)

    response = table.scan(FilterExpression=Attr("sk").eq("STUDY")) if Attr else table.scan()
    items = response.get("Items", [])
    study_sets = [item for item in items if item.get("sk") == "STUDY"]
    return sorted(study_sets, key=lambda item: item["createdAt"], reverse=True)


def _get_study_set(table, study_id: str) -> Optional[Dict[str, Any]]:
    if table is None:
        return _memory_store["study_sets"].get(study_id)

    response = table.get_item(Key={"pk": study_id, "sk": "STUDY"})
    return response.get("Item")


def _get_text(table, study_id: str) -> Optional[str]:
    if table is None:
        return _memory_store["texts"].get(study_id)

    response = table.get_item(Key={"pk": study_id, "sk": "TEXT"})
    item = response.get("Item")
    return item.get("text") if item else None


def _get_quiz(table, study_id: str) -> Optional[Dict[str, Any]]:
    if table is None:
        return _memory_store.get("quizzes", {}).get(study_id)

    response = table.get_item(Key={"pk": study_id, "sk": "QUIZ"})
    return response.get("Item")


def _put_quiz(table, study_id: str, quiz: Dict[str, Any]) -> None:
    if table is None:
        if "quizzes" not in _memory_store:
            _memory_store["quizzes"] = {}
        _memory_store["quizzes"][study_id] = quiz
        return

    table.put_item(Item={"pk": study_id, "sk": "QUIZ", **quiz})


def _parse_body(event: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not event.get("body"):
        return None, None
    try:
        body = event["body"]
        if event.get("isBase64Encoded"):
            import base64

            body = base64.b64decode(body).decode("utf-8")
        return json.loads(body), None
    except Exception as exc:
        return None, str(exc)


def _route(method: str, path: str) -> Tuple[str, Optional[str]]:
    if path == "/uploads/presign":
        return "presign", None
    if path == "/study-sets/from-upload":
        return "from_upload", None
    if path == "/study-sets":
        return "study_sets", None
    if path.startswith("/study-sets/"):
        rest = path[len("/study-sets/") :]
        if rest.endswith("/quiz"):
            study_id = rest[: -len("/quiz")]
            return "quiz", study_id
        if rest.endswith("/validate"):
            study_id = rest[: -len("/validate")]
            return "validate", study_id
        return "study_set", rest
    return "not_found", None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        method = (
            event.get("requestContext", {}).get("http", {}).get("method")
            or event.get("httpMethod")
            or "GET"
        )
        path = event.get("rawPath") or event.get("path") or "/"

        if method == "OPTIONS":
            return _json_response(200, {"ok": True})

        route, study_id = _route(method, path)
        table = _get_table()

        if route == "study_sets" and method == "GET":
            return _json_response(200, _list_study_sets(table))

        if route == "study_sets" and method == "POST":
            body, error = _parse_body(event)
            if error:
                return _json_response(400, {"error": "Invalid JSON body"})
            text = (body or {}).get("text", "").strip()
            title = (body or {}).get("title")
            if not text:
                return _json_response(400, {"error": "text is required"})
            study_set = _create_study_set(title, text)
            _put_study_set(table, study_set, text)
            _store_chunks(table, study_set["id"], text)
            return _json_response(201, study_set)

        if route == "presign" and method == "POST":
            body, error = _parse_body(event)
            if error:
                return _json_response(400, {"error": "Invalid JSON body"})
            s3_client = _get_s3_client()
            if s3_client is None:
                return _json_response(400, {"error": "UPLOAD_BUCKET is not configured"})
            filename = (body or {}).get("filename", "upload.txt")
            content_type = _normalize_content_type(
                filename, (body or {}).get("contentType", "text/plain")
            )
            if content_type not in ALLOWED_CONTENT_TYPES:
                return _json_response(400, {"error": "Unsupported content type"})
            key = f"uploads/{uuid.uuid4()}_{filename}"
            try:
                url = s3_client.generate_presigned_url(
                    "put_object",
                    Params={"Bucket": UPLOAD_BUCKET, "Key": key, "ContentType": content_type},
                    ExpiresIn=300,
                )
            except Exception:
                return _json_response(500, {"error": "Failed to create presigned URL"})
            return _json_response(200, {"url": url, "key": key})

        if route == "from_upload" and method == "POST":
            body, error = _parse_body(event)
            if error:
                return _json_response(400, {"error": "Invalid JSON body"})
            key = (body or {}).get("key", "").strip()
            title = (body or {}).get("title")
            if not key:
                return _json_response(400, {"error": "key is required"})
            s3_client = _get_s3_client()
            if s3_client is None:
                return _json_response(400, {"error": "UPLOAD_BUCKET is not configured"})
            try:
                obj = s3_client.get_object(Bucket=UPLOAD_BUCKET, Key=key)
                data = obj["Body"].read()
                content_type = obj.get("ContentType", "text/plain")
                filename = key.split("/")[-1]
                text, extract_error = _extract_text_from_upload(data, content_type, filename)
                if extract_error:
                    return _json_response(400, {"error": extract_error})
            except Exception:
                return _json_response(500, {"error": "Failed to read upload"})
            if not text.strip():
                return _json_response(400, {"error": "Uploaded file was empty"})
            study_set = _create_study_set(title, text, source_type="upload")
            _put_study_set(table, study_set, text)
            _store_chunks(table, study_set["id"], text)
            return _json_response(201, study_set)

        if route == "study_set" and study_id and method == "GET":
            study_set = _get_study_set(table, study_id)
            if not study_set:
                return _json_response(404, {"error": "Study set not found"})
            return _json_response(200, study_set)

        if route == "quiz" and study_id and method == "POST":
            existing = _get_quiz(table, study_id)
            if existing:
                return _json_response(200, existing)
            text = _get_text(table, study_id)
            if not text:
                return _json_response(404, {"error": "Study set text not found"})
            quiz_data = _generate_quiz_with_llm(table, study_id, text)
            if not quiz_data or "quiz" not in quiz_data:
                if isinstance(quiz_data, dict) and "_raw" in quiz_data:
                    raw = quiz_data["_raw"]
                    return _json_response(
                        500,
                        {
                            "error": "Failed to parse quiz JSON from model output",
                            "modelOutput": raw[:4000],
                            "modelId": TITAN_TEXT_MODEL_ID,
                        },
                    )
                if isinstance(quiz_data, dict) and "_error" in quiz_data:
                    return _json_response(
                        500,
                        {"error": quiz_data["_error"], "modelId": TITAN_TEXT_MODEL_ID},
                    )
                return _json_response(
                    500,
                    {"error": "Failed to generate quiz", "modelId": TITAN_TEXT_MODEL_ID},
                )
            quiz = {"quiz": quiz_data["quiz"], "updatedAt": _now_iso()}
            if isinstance(quiz_data, dict) and quiz_data.get("_fallback"):
                quiz["fallbackUsed"] = True
            if DEBUG_MODEL_OUTPUT and isinstance(quiz_data, dict) and "_raw" in quiz_data:
                quiz["modelOutput"] = str(quiz_data["_raw"])[:4000]
            _put_quiz(table, study_id, quiz)
            return _json_response(200, quiz)

        if route == "validate" and study_id and method == "POST":
            body, error = _parse_body(event)
            if error:
                return _json_response(400, {"error": "Invalid JSON body"})
            answers = (body or {}).get("answers", [])
            if not isinstance(answers, list):
                return _json_response(400, {"error": "answers must be an array"})
            quiz = _get_quiz(table, study_id)
            if not quiz:
                return _json_response(404, {"error": "Quiz not found"})
            questions = quiz.get("quiz", [])
            normalized = _normalize_answers(answers, len(questions))
            results = []
            correct = 0
            for idx, question in enumerate(questions):
                correct_index = question.get("answerIndex")
                user_index = normalized[idx]
                is_correct = user_index == correct_index
                if is_correct:
                    correct += 1
                results.append(
                    {
                        "questionIndex": idx,
                        "isCorrect": is_correct,
                        "correctAnswerIndex": correct_index,
                        "userAnswerIndex": user_index,
                        "feedback": question.get("explanation", ""),
                    }
                )
            total = len(questions)
            percentage = int((correct / total) * 100) if total else 0
            return _json_response(
                200,
                {
                    "results": results,
                    "score": {"correct": correct, "total": total, "percentage": percentage},
                },
            )

        return _json_response(404, {"error": "Not found"})
    except Exception as exc:
        return _json_response(500, {"error": str(exc)})
