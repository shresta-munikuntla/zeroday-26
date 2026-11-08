"""Shared Chroma/model access and request-local retrieval provenance."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache

from backend import config

_receipt = ContextVar('retrieved_sources', default=None)


def get_client():
    import chromadb
    return chromadb.PersistentClient(path=config.chroma_path())


def get_collection():
    from chromadb.errors import NotFoundError
    try:
        return get_client().get_collection('knowledge')
    except NotFoundError:
        return None


def rebuild_collection():
    from chromadb.errors import NotFoundError
    client = get_client()
    try:
        client.delete_collection('knowledge')
    except NotFoundError:
        pass
    return client.create_collection('knowledge')


@lru_cache(maxsize=1)
def get_model(name):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name)


def record_results(sources):
    receipt = _receipt.get()
    if receipt is not None:
        receipt.extend(dict(source) for source in sources)


@contextmanager
def capture_sources():
    """Capture only documents actually retrieved during this agent invocation."""
    sources = []
    token = _receipt.set(sources)
    try:
        yield sources
    finally:
        _receipt.reset(token)


_validation_receipt = ContextVar('intelligence_validation', default=None)


def record_validation(status):
    receipt = _validation_receipt.get()
    if receipt is not None:
        receipt.append(status)


@contextmanager
def capture_validations():
    statuses = []
    token = _validation_receipt.set(statuses)
    try:
        yield statuses
    finally:
        _validation_receipt.reset(token)
