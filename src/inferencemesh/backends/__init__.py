"""Serving backend adapters."""

from inferencemesh.backends.base import BackendAdapter, BackendCompletion
from inferencemesh.backends.fake import FakeBackend

__all__ = ["BackendAdapter", "BackendCompletion", "FakeBackend"]
