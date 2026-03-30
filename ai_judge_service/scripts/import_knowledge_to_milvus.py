#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.milvus_indexer import MilvusIndexerConfig, import_knowledge_to_milvus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import knowledge JSON into Milvus with OpenAI embeddings.",
    )
    parser.add_argument("--input-file", required=True, help="Knowledge JSON file path")
    parser.add_argument("--milvus-uri", required=True, help="Milvus URI")
    parser.add_argument("--milvus-collection", required=True, help="Milvus collection")
    parser.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    parser.add_argument(
        "--openai-base-url",
        default=os.getenv("AI_JUDGE_OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("AI_JUDGE_RAG_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
    )
    parser.add_argument("--openai-timeout-secs", type=float, default=15.0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--milvus-token", default=os.getenv("AI_JUDGE_RAG_MILVUS_TOKEN", ""))
    parser.add_argument("--milvus-db-name", default=os.getenv("AI_JUDGE_RAG_MILVUS_DB_NAME", ""))
    parser.add_argument("--ensure-collection", action="store_true")
    parser.add_argument("--metric-type", default="COSINE")
    parser.add_argument("--vector-field", default="embedding")
    parser.add_argument("--chunk-id-field", default="chunk_id")
    parser.add_argument("--title-field", default="title")
    parser.add_argument("--source-url-field", default="source_url")
    parser.add_argument("--content-field", default="content")
    parser.add_argument("--tags-field", default="tags")
    parser.add_argument(
        "--embed-input-max-tokens",
        type=int,
        default=int(os.getenv("AI_JUDGE_EMBED_INPUT_MAX_TOKENS", "2000")),
    )
    parser.add_argument(
        "--tokenizer-model",
        default=os.getenv("AI_JUDGE_OPENAI_MODEL", "gpt-4.1-mini"),
    )
    parser.add_argument(
        "--tokenizer-fallback-encoding",
        default=os.getenv("AI_JUDGE_TOKENIZER_FALLBACK_ENCODING", "o200k_base"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cfg = MilvusIndexerConfig(
        input_file=args.input_file,
        milvus_uri=args.milvus_uri,
        milvus_collection=args.milvus_collection,
        openai_api_key=args.openai_api_key,
        openai_base_url=args.openai_base_url,
        openai_embedding_model=args.embedding_model,
        openai_timeout_secs=args.openai_timeout_secs,
        batch_size=args.batch_size,
        milvus_token=args.milvus_token,
        milvus_db_name=args.milvus_db_name,
        ensure_collection=args.ensure_collection,
        metric_type=args.metric_type,
        vector_field=args.vector_field,
        chunk_id_field=args.chunk_id_field,
        title_field=args.title_field,
        source_url_field=args.source_url_field,
        content_field=args.content_field,
        tags_field=args.tags_field,
        embed_input_max_tokens=args.embed_input_max_tokens,
        tokenizer_model=args.tokenizer_model,
        tokenizer_fallback_encoding=args.tokenizer_fallback_encoding,
    )
    stats = import_knowledge_to_milvus(cfg)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
