"""Artifact store adapters."""

from .local_store import LocalArtifactStore
from .s3_store import S3CompatibleArtifactStore

__all__ = ["LocalArtifactStore", "S3CompatibleArtifactStore"]
