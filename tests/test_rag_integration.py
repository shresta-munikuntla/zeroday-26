"""Opt-in real model/Chroma verification, isolated from the development index.

Run with SENTINELAI_RUN_RAG_INTEGRATION=1. The model must be cached or downloadable.
No Nemotron key or API call is used.
"""
import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv('SENTINELAI_RUN_RAG_INTEGRATION') != '1',
    reason='Set SENTINELAI_RUN_RAG_INTEGRATION=1 to run real embedding integration',
)


def test_real_index_retrieval_and_agent_fallback(monkeypatch, tmp_path):
    import chromadb
    from backend import config
    from backend.rag.ingest import ingest, read_chunks
    from backend.rag.retrieve import search_knowledge
    from backend.agents.intelligence import analyze, AI_UNAVAILABLE, NO_SOURCES
    from backend.agents.intelligence_contract import IntelligenceOutput

    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', str(tmp_path / 'chroma'))
    monkeypatch.setattr(config, 'NEMOTRON_API_KEY', '')
    assert search_knowledge('SSH') == []
    client = chromadb.PersistentClient(path=config.chroma_path())
    client.create_collection('knowledge')
    assert search_knowledge('SSH') == []
    assert ingest(True) == (12, 39, [])
    assert client.get_collection('knowledge').get(where={'doc_id': 'POL-099'})['ids']
    assert ingest() == (11, 38, [])
    collection = client.get_collection('knowledge')
    assert collection.count() == 38
    assert collection.get(where={'doc_id': 'POL-099'})['ids'] == []
    actual = collection.get(include=['documents', 'metadatas'])
    stored = dict(zip(actual['ids'], zip(actual['documents'], actual['metadatas'])))
    _, expected, _ = read_chunks(config.ROOT / 'data/knowledge')
    for chunk in expected:
        text, metadata = stored[f"{chunk['doc_id']}#{chunk['section']}"]
        assert text == chunk['text']
        assert metadata == {key: value for key, value in chunk.items() if key != 'text'}
    print('Verified all 38 stored chunks, metadata, fixture inclusion and clean rebuild.')
    cases = [
        ('expired SSH permissions privileged account', 'internal_policy_sample', 3),
        ('privileged valid account SSH external remote services', 'mitre_attack_official', 3),
        ('external IP expired SSH permission database denied', 'historical_incident_sample', 2),
    ]
    for query, kind, limit in cases:
        results = search_knowledge(query, {'source_type': kind}, limit)
        assert 0 < len(results) <= limit
        assert all(item['source_type'] == kind for item in results)
        assert all(item['score'] >= 0.4 for item in results)
        print(query, [(r['doc_id'], round(r['score'], 4)) for r in results])
    for query in ('how to bake a chocolate cake', 'football match ticket prices'):
        assert search_knowledge(query) == []
    root = Path(__file__).resolve().parents[1]
    investigation = json.loads((root / 'tests/fixtures/investigation_placeholder.json').read_text())
    original = json.dumps(investigation, sort_keys=True)
    result = analyze(investigation)
    IntelligenceOutput.model_validate(result)
    assert AI_UNAVAILABLE in result['limitations']
    assert result['recommended_actions']
    assert all(item['source_document_ids'] for item in result['recommended_actions'])
    assert json.dumps(investigation, sort_keys=True) == original
    assert 'POL-099' not in json.dumps(result)
    print('Real Agent 3 placeholder-fixture fallback:', json.dumps(result, indent=2))
    # Removing all sources must produce the exact no-source limitation.
    client.delete_collection('knowledge')
    empty = analyze(investigation)
    assert NO_SOURCES in empty['limitations']
    assert not empty['recommended_actions']
