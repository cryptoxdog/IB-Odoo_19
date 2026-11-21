"""Synthetic DeepSeek API responses for the offline adapter tests (TASK-068).

Shaped by the DeepSeek API documentation (EVID-012: ``guides/responses_api.md``,
``guides/files_api.md``). Every id and value is synthetic: no key, no real document and no
recorded live payload. The UNK-006 live probe replaces these with redacted recordings only after
it has run on Staging with synthetic documents.
"""

RESPONSE_MESSAGE = {
    "id": "resp_synthetic_0001",
    "object": "response",
    "model": "deepseek-flash",
    "status": "completed",
    "store": False,
    "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "done"}]}],
    "usage": {"input_tokens": 120, "output_tokens": 3, "output_tokens_details": {"reasoning_tokens": 0}},
}

RESPONSE_FUNCTION_CALL = {
    "id": "resp_synthetic_0002",
    "object": "response",
    "model": "deepseek-flash",
    "status": "completed",
    "store": False,
    "output": [
        {
            "type": "function_call",
            "call_id": "call_synthetic_0001",
            "name": "ir_actions_server_add_tags",
            "arguments": '{"tag_names": ["BOL"]}',
        }
    ],
    "usage": {"input_tokens": 140, "output_tokens": 18, "output_tokens_details": {"reasoning_tokens": 0}},
}

FILE_UPLOADED = {
    "id": "file-api-synthetic0001",
    "object": "file",
    "bytes": 2048,
    "created_at": 1700000000,
    "filename": "file_1.pdf",
    "purpose": "rich_layout_recognition",
    "expires_at": 1700003600,
}

FILE_DELETED = {"id": "file-api-synthetic0001", "object": "file", "deleted": True}

ERROR_RATE_LIMITED = {"error": {"message": "Synthetic rate limit reached for requests", "type": "rate_limit_error"}}

FIXTURES = {
    "response_message.json": RESPONSE_MESSAGE,
    "response_function_call.json": RESPONSE_FUNCTION_CALL,
    "file_uploaded.json": FILE_UPLOADED,
    "file_deleted.json": FILE_DELETED,
    "error_rate_limited.json": ERROR_RATE_LIMITED,
}
