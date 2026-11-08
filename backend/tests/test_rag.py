"""Required RAG test entrypoint, including real persistence when opted in."""
import os
from pathlib import Path

import pytest

from backend.rag.ingest import parse_document, read_chunks
from backend.rag.vector_store import capture_sources, record_results
from backend.rag.retrieve import search_knowledge

ROOT = Path(__file__).resolve().parents[2]


def test_metadata_sections_and_stable_chunk_ids():
    documents, chunks, errors = read_chunks(ROOT / 'data/knowledge')
    assert documents == 11 and not errors and len(chunks) == 38
    assert {c['source_type'] for c in chunks} == {'mitre_attack_official', 'internal_policy_sample', 'historical_incident_sample'}
    assert len({f"{c['doc_id']}#{c['section']}" for c in chunks}) == 38
    assert not any(c['doc_id'] == 'POL-099' for c in chunks)
    _, included, errors = read_chunks(ROOT / 'data/knowledge', True)
    assert not errors and any(c['doc_id'] == 'POL-099' for c in included)
    metadata, sections = parse_document('---\ndoc_id: ID\ntitle: "Title"\nsource_type: test\n---\n## A\nOne\n## B\nTwo')
    assert metadata['title'] == 'Title'
    assert [c['section'] for c in sections] == ['A', 'B']


def test_provenance_scoped_and_isolated():
    with capture_sources() as outer:
        record_results([{'doc_id': 'POL-001'}])
        with capture_sources() as inner:
            record_results([{'doc_id': 'CASE-002'}])
        record_results([{'doc_id': 'POL-003'}])
    record_results([{'doc_id': 'MUST-NOT-LEAK'}])
    assert [s['doc_id'] for s in outer] == ['POL-001', 'POL-003']
    assert [s['doc_id'] for s in inner] == ['CASE-002']


@pytest.mark.skipif(os.getenv('SENTINELAI_RUN_RAG_INTEGRATION') != '1', reason='Opt-in real embeddings')
def test_real_inc001_sources_threshold_and_nonsense(monkeypatch, tmp_path):
    from backend import config
    from backend.rag.ingest import ingest
    from backend.rag.vector_store import get_collection
    from backend.agents.intelligence import analyze, NO_SOURCES
    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', str(tmp_path / 'chroma'))
    monkeypatch.setattr(config, 'NEMOTRON_API_KEY', '')
    assert ingest() == (11, 38, [])
    assert ingest() == (11, 38, [])
    assert get_collection().count() == 38
    # Include the incident identifier and the actual evidence semantics; a bare
    # identifier has no semantic meaning in the document-only knowledge index.
    query = 'INC-001 privileged account uses valid accounts for external remote services and SSH'
    mitre = search_knowledge(query, {'source_type': 'mitre_attack_official'}, 3)
    policies = search_knowledge(query, {'source_type': 'internal_policy_sample'}, 3)
    cases = search_knowledge(query, {'source_type': 'historical_incident_sample'}, 2)
    assert 'MITRE-T1078' in {r['doc_id'] for r in mitre}
    assert {'POL-001', 'POL-002', 'POL-003'} & {r['doc_id'] for r in policies}
    assert 'CASE-002' in {r['doc_id'] for r in cases}
    assert all(r['score'] >= 0.4 for r in mitre + policies + cases)
    assert len(mitre) <= 3 and len(policies) <= 3 and len(cases) <= 2
    assert search_knowledge('purple banana intergalactic chocolate cake football tickets') == []
    assert search_knowledge('chocolate cake recipe') == []
    literal_nonsense = analyze({'status': 'chocolate cake recipe',
                               'confirmed_facts': [], 'investigation_reasons': []})
    assert NO_SOURCES in literal_nonsense['limitations']
    assert not literal_nonsense['recommended_actions']
    result = analyze({'status': 'purple banana intergalactic chocolate cake',
                      'confirmed_facts': [], 'investigation_reasons': ['football tickets']})
    assert NO_SOURCES in result['limitations']
    assert not result['recommended_actions']
