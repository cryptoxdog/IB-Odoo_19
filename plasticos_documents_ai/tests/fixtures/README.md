# Synthetic DeepSeek fixtures

`deepseek_responses.py` holds the responses the offline adapter tests replay. They are shaped by the DeepSeek API documentation (EVID-012: `guides/responses_api.md`, `guides/files_api.md`).

- Every id and value is synthetic.
- No key, no real document and no recorded live payload is stored here.
- The UNK-006 live probe will replace these with redacted recordings, but only after it has run on Staging with synthetic documents.
