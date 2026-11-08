import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend import config
from backend.rag import retrieve


@pytest.fixture
def index(monkeypatch, tmp_path):
    class NotFoundError(Exception):
        pass
    collection = Mock()
    collection.count.return_value = 8
    collection.query.return_value = {
        'metadatas': [[{'doc_id': 'POL-003', 'title': 'Policy', 'section': 'Expired', 'source_type': 'internal_policy_sample'}]],
        'documents': [['original text']], 'distances': [[1.0]],
    }
    client = Mock()
    client.get_collection.return_value = collection
    monkeypatch.setitem(sys.modules, 'chromadb', SimpleNamespace(PersistentClient=lambda path: client))
    monkeypatch.setitem(sys.modules, 'chromadb.errors', SimpleNamespace(NotFoundError=NotFoundError))
    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', str(tmp_path))
    model = Mock()
    model.encode.return_value.tolist.return_value = [[1.0]]
    monkeypatch.setattr(retrieve, '_model', lambda name: model)
    return collection, client, NotFoundError


def test_relevant_original_text_and_score(index):
    collection, _, _ = index
    result = retrieve.search_knowledge('expired SSH permission')
    assert result == [{'doc_id': 'POL-003', 'title': 'Policy', 'section': 'Expired', 'source_type': 'internal_policy_sample', 'url': None, 'text': 'original text', 'score': 0.5}]
    assert collection.query.call_args.kwargs['n_results'] == 5


def test_filter_and_limit(index):
    collection, _, _ = index
    result = retrieve.search_knowledge('SSH', {'source_type': 'mitre_attack_official'}, 3)
    assert len(result) <= 3
    assert collection.query.call_args.kwargs['where'] == {'source_type': 'mitre_attack_official'}
    assert collection.query.call_args.kwargs['n_results'] == 3
    retrieve.search_knowledge('SSH', k=100)
    assert collection.query.call_args.kwargs['n_results'] == 8


@pytest.mark.parametrize('distance,expected', [(0.5, 1), (1.5, 1), (1.5001, 0), (1.8526, 0), (float('nan'), 0)])
def test_threshold(index, distance, expected):
    collection, _, _ = index
    collection.query.return_value['distances'] = [[distance]]
    assert len(retrieve.search_knowledge('query')) == expected


def test_no_matching_results(index):
    collection, _, _ = index
    collection.query.return_value = {'metadatas': [[]], 'documents': [[]], 'distances': [[]]}
    assert retrieve.search_knowledge('query') == []


def test_empty_collection(index):
    collection, _, _ = index
    collection.count.return_value = 0
    assert retrieve.search_knowledge('query') == []
    collection.query.assert_not_called()


def test_missing_collection(index):
    _, client, error = index
    client.get_collection.side_effect = error()
    assert retrieve.search_knowledge('query') == []


def test_unconfigured_and_zero_limit(index, monkeypatch):
    assert retrieve.search_knowledge('query', k=0) == []
    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', '')
    assert retrieve.search_knowledge('query') == []


def test_duplicate_search_chunks_are_returned_once(index):
    collection, _, _ = index
    result = collection.query.return_value
    for key in ('metadatas', 'documents', 'distances'):
        result[key][0] *= 2
    assert len(retrieve.search_knowledge('expired permission')) == 1
