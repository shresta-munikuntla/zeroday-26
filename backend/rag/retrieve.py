"""Semantic retrieval with a distance cutoff measured on the repository corpus."""
import math

from backend import config
from backend.rag import vector_store

# Chroma's default squared-L2 distance, converted to 1 / (1 + distance).
# Measured relevant top-five distances: 0.5474..1.1448; unrelated nearest
# distances: 1.8526..1.9559. The gap midpoint is ~1.499 (score ~0.4002).
# See docs/p2-verification.md for the queries and calibration limitations.
MIN_SIMILARITY = 0.4


def _model(name):
    return vector_store.get_model(name)


def search_knowledge(query: str, filters: dict | None = None, k: int = 5) -> list[dict]:
    if k <= 0 or not query.strip() or not config.CHROMA_PERSIST_DIRECTORY:
        return []
    collection = vector_store.get_collection()
    if collection is None:
        return []
    count = collection.count()
    if count == 0:
        return []
    kwargs = {}
    if filters and 'source_type' in filters:
        kwargs['where'] = {'source_type': filters['source_type']}
    result = collection.query(
        query_embeddings=_model(config.EMBEDDING_MODEL).encode([query]).tolist(),
        n_results=min(k, count), include=['documents', 'metadatas', 'distances'],
        **kwargs,
    )
    matches = []
    for metadata, text, distance in zip(result['metadatas'][0], result['documents'][0], result['distances'][0]):
        if not math.isfinite(distance) or distance < 0:
            continue
        score = 1.0 / (1.0 + distance)
        if score >= MIN_SIMILARITY:
            matches.append({key: metadata.get(key, '') for key in
                            ('doc_id', 'title', 'section', 'source_type', 'url')} |
                           {'text': text, 'score': score})
    return matches[:k]
