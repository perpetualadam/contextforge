# Backup and restore (indexes & memories)

## Vector index (FAISS + metadata)

- **Data path (default):** `data/vector_index/` (Docker volume `./data/vector_index` → `/app/data` in containers).
- **Backup:** Stop writers or snapshot the directory while idle; copy `faiss_index.bin`, `metadata.json`, `lexical_index.json`, `code_graph.json` if present.
- **Restore:** Place files back under the same paths, restart `vector-index` and `api_gateway`.

## Workspace memories

- **Path:** `data/workspace_memories/*.json` (override with `WORKSPACE_MEMORY_DIR`).

## Feedback / audit

- **Feedback:** `data/feedback/query_feedback.jsonl`
- **Audit:** `data/audit/audit.jsonl` (when `AUDIT_LOG_ENABLED=true`)

Version these paths in your own backup policy; the on-disk format is stable within a minor release.
