from pathlib import Path
from unittest.mock import Mock
import sys
import types

import pytest

from backend import config
from backend.rag.ingest import parse_document, read_chunks, ingest


ROOT = Path(__file__).resolve().parents[1] / 'data/knowledge'


def test_front_matter_and_sections():
    metadata, chunks = parse_document('---\ndoc_id: X\ntitle: "A title"\nsource_type: example\nurl: https://example.invalid\n---\n# ignored\n## First\nBody\n### Subheading\nmore\n## Second\nText')
    assert metadata['title'] == 'A title'
    assert [c['section'] for c in chunks] == ['First', 'Second']
    assert chunks[0]['text'] == 'Body\n### Subheading\nmore'
    assert chunks[0]['url'] == 'https://example.invalid'
    assert chunks[1]['doc_id'] == 'X'


@pytest.mark.parametrize('text', ['## No metadata', '---\ndoc_id: X', '---\ntitle: X\n---\n## Section\nBody'])
def test_invalid_documents(text):
    with pytest.raises(ValueError):
        parse_document(text)


def test_actual_metadata_ids_and_fixture_exclusion():
    documents, chunks, errors = read_chunks(ROOT)
    assert documents == 11
    assert not errors
    assert 'POL-099' not in {c['doc_id'] for c in chunks}
    assert {c['source_type'] for c in chunks} == {'mitre_attack_official', 'internal_policy_sample', 'historical_incident_sample'}
    assert len({f"{c['doc_id']}#{c['section']}" for c in chunks}) == len(chunks)
    assert chunks == read_chunks(ROOT)[1]
    assert all('LOG-' not in c['doc_id'] for c in chunks)
    documents, included, errors = read_chunks(ROOT, True)
    assert documents == 12 and not errors
    assert any(c['doc_id'] == 'POL-099' for c in included)


def test_rebuild_and_stable_ids(monkeypatch, tmp_path):
    class NotFoundError(Exception):
        pass
    stored = {}
    class Client:
        def delete_collection(self, name):
            stored.clear()
        def create_collection(self, name):
            assert name == 'knowledge'
            return self
        def add(self, ids, documents, embeddings, metadatas):
            stored.update(zip(ids, metadatas))
        def count(self):
            return len(stored)
    monkeypatch.setitem(sys.modules, 'chromadb', types.SimpleNamespace(PersistentClient=lambda path: Client()))
    monkeypatch.setitem(sys.modules, 'chromadb.errors', types.SimpleNamespace(NotFoundError=NotFoundError))
    embeddings = Mock()
    embeddings.encode.return_value.tolist.return_value = [[1.0]]
    monkeypatch.setitem(sys.modules, 'sentence_transformers', types.SimpleNamespace(SentenceTransformer=lambda name: embeddings))
    from backend.rag import vector_store
    monkeypatch.setattr(vector_store, 'get_model', lambda name: embeddings)
    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', str(tmp_path))
    ingest(True)
    assert any(k.startswith('POL-099#') for k in stored)
    ingest()
    first = stored.copy()
    ingest()
    assert stored == first
    assert not any(k.startswith('POL-099#') for k in stored)
    assert 'MITRE-T1078#Description' in stored


def test_preserve_ids_and_empty_sections():
    metadata, chunks = parse_document("---\ndoc_id: DOC'\ntitle: Example\nsource_type: example\n---\n## Empty\n## Next\nBody")
    assert metadata['doc_id'] == "DOC'"
    assert chunks[0]['text'] == ''
    assert [chunk['section'] for chunk in chunks] == ['Empty', 'Next']


@pytest.mark.parametrize('include', [False, True])
def test_cli_fixture_flag(monkeypatch, include):
    from backend.rag import ingest as module
    runner = Mock()
    monkeypatch.setattr(module, 'ingest', runner)
    monkeypatch.setattr(sys, 'argv', ['ingest'] + (['--include-test-fixtures'] if include else []))
    module.main()
    runner.assert_called_once_with(include)
