from __future__ import annotations

import hashlib
import json
import math
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .action_gates import utc_now
from .contracts import ContractRegistry, REPO_ROOT


DEFAULT_KNOWLEDGE_INDEX_PATH = REPO_ROOT / "state" / "knowledge-index.json"
TOKEN_PATTERN = re.compile(r"[A-Za-zА-Яа-я0-9_-]+")


class KnowledgeConnector(Protocol):
    def sync(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        ...


@dataclass(frozen=True)
class SourceSyncResult:
    source_id: str
    status: str
    documents: list[dict[str, Any]]
    message: str | None = None
    error: dict[str, str] | None = None


class LocalFilesConnector:
    def __init__(
        self,
        contracts: ContractRegistry,
        repo_root: Path = REPO_ROOT,
    ):
        self.contracts = contracts
        self.repo_root = repo_root

    def sync(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        source_root = self._source_root(source)
        if not source_root.exists():
            return []

        include_globs = source.get("include_globs") or ["*.md", "*.txt"]
        files: list[Path] = []
        for pattern in include_globs:
            files.extend(source_root.rglob(pattern))

        documents = []
        for path in sorted(set(files)):
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue

            relative_path = path.relative_to(self.repo_root)
            metadata = {
                **source.get("metadata", {}),
                "path": str(relative_path),
                **self._extract_metadata(content),
            }
            document = {
                "schema_version": "1.0",
                "document_id": f"{source['source_id']}:{relative_path.as_posix()}",
                "source_id": source["source_id"],
                "source_type": source["source_type"],
                "title": self._title_for(path, content),
                "uri": relative_path.as_posix(),
                "content": content,
                "content_checksum": self._checksum(content),
                "content_version": self._checksum(content)[:16],
                "updated_at": utc_now(),
                "metadata": metadata,
            }
            self.contracts.require_valid("knowledge_document", document)
            documents.append(document)
        return documents

    def _source_root(self, source: dict[str, Any]) -> Path:
        configured_path = Path(source["path"])
        if configured_path.is_absolute():
            return configured_path
        return self.repo_root / configured_path

    @staticmethod
    def _title_for(path: Path, content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip() or path.stem
            if stripped:
                break
        return path.stem.replace("-", " ").replace("_", " ").strip() or path.name

    @staticmethod
    def _extract_metadata(content: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for line in content.splitlines()[:20]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized_key = key.strip().lower().replace(" ", "_")
            normalized_value = value.strip()
            if normalized_key in {"service", "environment", "owner_team"} and normalized_value:
                metadata[normalized_key] = normalized_value
            if normalized_key == "labels" and normalized_value:
                metadata["labels"] = [
                    item.strip()
                    for item in normalized_value.split(",")
                    if item.strip()
                ]
        return metadata

    @staticmethod
    def _checksum(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class KnowledgeIndexer:
    def __init__(
        self,
        contracts: ContractRegistry,
        index_path: str | Path | None = None,
    ):
        self.contracts = contracts
        configured_path = index_path or os.getenv("KNOWLEDGE_INDEX_PATH")
        self.index_path = Path(configured_path) if configured_path else DEFAULT_KNOWLEDGE_INDEX_PATH
        self.connectors: dict[str, KnowledgeConnector] = {
            "local_files": LocalFilesConnector(contracts),
        }

    def rebuild(self, operator_id: str) -> dict[str, Any]:
        started_at = utc_now()
        index_id = f"kb-{uuid.uuid4().hex[:12]}"
        documents: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []
        source_stats: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for source in self.contracts.knowledge_source_catalog["sources"]:
            source_result = self._sync_source(source)
            if source_result.error:
                errors.append(source_result.error)

            source_chunks = []
            for document in source_result.documents:
                document_chunks = self._chunk_document(document)
                source_chunks.extend(document_chunks)

            documents.extend(source_result.documents)
            chunks.extend(source_chunks)
            source_stat = {
                "source_id": source_result.source_id,
                "status": source_result.status,
                "document_count": len(source_result.documents),
                "chunk_count": len(source_chunks),
            }
            if source_result.message:
                source_stat["message"] = source_result.message
            source_stats.append(source_stat)

        status = self._manifest_status(chunks, errors)
        manifest = {
            "schema_version": "1.0",
            "index_id": index_id,
            "status": status,
            "built_at": started_at,
            "requested_by_operator": operator_id,
            "source_count": len(source_stats),
            "document_count": len(documents),
            "chunk_count": len(chunks),
            "sources": source_stats,
            "errors": errors,
        }
        self.contracts.require_valid("knowledge_index_manifest", manifest)

        index = {
            "schema_version": "1.0",
            "manifest": manifest,
            "documents": documents,
            "chunks": chunks,
        }
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        result = {
            "schema_version": "1.0",
            "status": status,
            "index_manifest": manifest,
            "index_path": str(self.index_path),
        }
        self.contracts.require_valid("knowledge_rebuild_result", result)
        return result

    def status(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {
                "schema_version": "1.0",
                "status": "unavailable",
                "index_path": str(self.index_path),
                "error": {
                    "code": "knowledge_index_missing",
                    "message": f"Индекс базы знаний не найден: {self.index_path}",
                },
            }

        try:
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
            manifest = index["manifest"]
            self.contracts.require_valid("knowledge_index_manifest", manifest)
        except (OSError, KeyError, json.JSONDecodeError) as error:
            return {
                "schema_version": "1.0",
                "status": "error",
                "index_path": str(self.index_path),
                "error": {
                    "code": "knowledge_index_invalid",
                    "message": str(error),
                },
            }

        return {
            "schema_version": "1.0",
            "status": manifest["status"],
            "index_path": str(self.index_path),
            "index_manifest": manifest,
        }

    def source_catalog(self) -> dict[str, Any]:
        return self.contracts.knowledge_source_catalog

    def chunks(self, *, source_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        index_result = self._read_index()
        if "error" in index_result:
            return index_result

        chunks = index_result["chunks"]
        if source_id:
            chunks = [
                chunk
                for chunk in chunks
                if chunk["source_id"] == source_id
            ]
        limited_chunks = chunks[: max(min(limit, 200), 0)]
        for chunk in limited_chunks:
            self.contracts.require_valid("knowledge_chunk", chunk)
        return {
            "schema_version": "1.0",
            "status": "success",
            "index_path": str(self.index_path),
            "index_manifest": index_result["manifest"],
            "source_id": source_id,
            "limit": limit,
            "total_matches": len(chunks),
            "chunks": limited_chunks,
        }

    def _read_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {
                "schema_version": "1.0",
                "status": "unavailable",
                "index_path": str(self.index_path),
                "error": {
                    "code": "knowledge_index_missing",
                    "message": f"Индекс базы знаний не найден: {self.index_path}",
                },
            }

        try:
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
            manifest = index["manifest"]
            documents = index["documents"]
            chunks = index["chunks"]
            self.contracts.require_valid("knowledge_index_manifest", manifest)
        except (OSError, KeyError, json.JSONDecodeError) as error:
            return {
                "schema_version": "1.0",
                "status": "error",
                "index_path": str(self.index_path),
                "error": {
                    "code": "knowledge_index_invalid",
                    "message": str(error),
                },
            }

        return {
            "schema_version": "1.0",
            "status": manifest["status"],
            "index_path": str(self.index_path),
            "manifest": manifest,
            "documents": documents,
            "chunks": chunks,
        }

    def _sync_source(self, source: dict[str, Any]) -> SourceSyncResult:
        if not source["enabled"]:
            return SourceSyncResult(
                source_id=source["source_id"],
                status="skipped",
                documents=[],
                message=source.get("disabled_reason", "Источник отключен."),
            )

        connector = self.connectors.get(source["connector_type"])
        if connector is None:
            return SourceSyncResult(
                source_id=source["source_id"],
                status="error",
                documents=[],
                error={
                    "source_id": source["source_id"],
                    "code": "connector_not_implemented",
                    "message": f"Коннектор не реализован: {source['connector_type']}",
                },
            )

        try:
            documents = connector.sync(source)
        except OSError as error:
            return SourceSyncResult(
                source_id=source["source_id"],
                status="error",
                documents=[],
                error={
                    "source_id": source["source_id"],
                    "code": "source_sync_failed",
                    "message": str(error),
                },
            )

        return SourceSyncResult(
            source_id=source["source_id"],
            status="success",
            documents=documents,
        )

    def _chunk_document(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        chunks = []
        for index, text in enumerate(self._split_content(document["content"])):
            chunk = {
                "schema_version": "1.0",
                "chunk_id": f"{document['document_id']}#chunk-{index}",
                "document_id": document["document_id"],
                "source_id": document["source_id"],
                "source_type": document["source_type"],
                "title": document["title"],
                "uri": document["uri"],
                "content": text,
                "content_checksum": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "chunk_index": index,
                "metadata": document["metadata"],
            }
            self.contracts.require_valid("knowledge_chunk", chunk)
            chunks.append(chunk)
        return chunks

    @staticmethod
    def _split_content(content: str, max_chars: int = 1200) -> list[str]:
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", content)
            if paragraph.strip()
        ]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = paragraph
        if current:
            chunks.append(current)
        return chunks or [content[:max_chars]]

    @staticmethod
    def _manifest_status(
        chunks: list[dict[str, Any]],
        errors: list[dict[str, str]],
    ) -> str:
        if errors and not chunks:
            return "failed"
        if errors:
            return "partial"
        return "success"


class KnowledgeRetriever:
    def __init__(
        self,
        contracts: ContractRegistry,
        index_path: str | Path | None = None,
    ):
        self.contracts = contracts
        configured_path = index_path or os.getenv("KNOWLEDGE_INDEX_PATH")
        self.index_path = Path(configured_path) if configured_path else DEFAULT_KNOWLEDGE_INDEX_PATH

    def retrieve(self, query: dict[str, Any]) -> dict[str, Any]:
        self.contracts.require_valid("retrieval_query", query)
        if not self.index_path.exists():
            return self._result(
                query,
                "unavailable",
                [],
                error={
                    "code": "knowledge_index_missing",
                    "message": f"Индекс базы знаний не найден: {self.index_path}",
                },
            )

        try:
            index = json.loads(self.index_path.read_text(encoding="utf-8"))
            manifest = index["manifest"]
            chunks = index["chunks"]
        except (OSError, KeyError, json.JSONDecodeError) as error:
            return self._result(
                query,
                "error",
                [],
                error={
                    "code": "knowledge_index_invalid",
                    "message": str(error),
                },
            )

        matches = self._rank_chunks(query, chunks)
        status = "success" if matches else "empty"
        return self._result(
            query,
            status,
            matches,
            index_id=manifest["index_id"],
            built_at=manifest["built_at"],
        )

    def build_query_from_ticket(self, ticket: dict[str, Any]) -> dict[str, Any]:
        parts = [
            str(ticket.get("service") or ""),
            str(ticket.get("environment") or ""),
            str(ticket.get("description") or ""),
            str(ticket.get("priority") or ""),
        ]
        query = " ".join(part for part in parts if part.strip()).strip() or "service desk ticket"
        filters = {}
        if ticket.get("service"):
            filters["service"] = str(ticket["service"])
        if ticket.get("environment"):
            filters["environment"] = str(ticket["environment"])
        result = {
            "schema_version": "1.0",
            "query": query,
            "top_k": 3,
        }
        if filters:
            result["filters"] = filters
        self.contracts.require_valid("retrieval_query", result)
        return result

    def _rank_chunks(
        self,
        query: dict[str, Any],
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        query_tokens = set(tokenize(query["query"]))
        if not query_tokens:
            return []
        filters = query.get("filters", {})
        top_k = query.get("top_k", 3)
        scored = []
        for chunk in chunks:
            if not self._matches_filters(chunk, filters):
                continue
            chunk_tokens = tokenize(f"{chunk['title']} {chunk['content']}")
            if not chunk_tokens:
                continue
            token_counts = {
                token: chunk_tokens.count(token)
                for token in set(chunk_tokens)
            }
            overlap = query_tokens.intersection(token_counts)
            if not overlap:
                continue
            score = sum(1 + math.log(token_counts[token]) for token in overlap)
            score += self._metadata_boost(chunk, filters)
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            self._match(score, chunk)
            for score, chunk in scored[:top_k]
        ]

    @staticmethod
    def _matches_filters(chunk: dict[str, Any], filters: dict[str, Any]) -> bool:
        metadata = chunk.get("metadata", {})
        source_ids = set(filters.get("source_ids") or [])
        if source_ids and chunk["source_id"] not in source_ids:
            return False
        labels = set(filters.get("labels") or [])
        chunk_labels = set(metadata.get("labels") or [])
        if labels and not labels.intersection(chunk_labels):
            return False
        return True

    @staticmethod
    def _metadata_boost(chunk: dict[str, Any], filters: dict[str, Any]) -> float:
        metadata = chunk.get("metadata", {})
        boost = 0.0
        for key in ("service", "environment"):
            expected = str(filters.get(key) or "").lower()
            actual = str(metadata.get(key) or "").lower()
            if expected and actual == expected:
                boost += 2.0
        return boost

    @staticmethod
    def _match(score: float, chunk: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_id": chunk["source_id"],
            "document_id": chunk["document_id"],
            "chunk_id": chunk["chunk_id"],
            "title": chunk["title"],
            "uri": chunk["uri"],
            "score": round(score, 4),
            "excerpt": excerpt(chunk["content"]),
            "metadata": chunk["metadata"],
        }

    def _result(
        self,
        query: dict[str, Any],
        status: str,
        matches: list[dict[str, Any]],
        *,
        index_id: str | None = None,
        built_at: str | None = None,
        error: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        result = {
            "schema_version": "1.0",
            "status": status,
            "query": query,
            "matches": matches,
        }
        if index_id:
            result["index_id"] = index_id
        if built_at:
            result["built_at"] = built_at
        if error:
            result["error"] = error
        self.contracts.require_valid("retrieval_result", result)
        return result


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if len(token) > 1
    ]


def excerpt(text: str, max_chars: int = 500) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max_chars - 3].rstrip()}..."
