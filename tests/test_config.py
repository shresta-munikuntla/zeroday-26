"""Check that empty template settings select usable offline defaults."""
import runpy
from unittest.mock import patch

import pytest

from backend import config


@pytest.mark.parametrize('blank', [False, True])
def test_offline_defaults(monkeypatch, blank):
    for name in ('NEMOTRON_BASE_URL', 'NEMOTRON_API_KEY', 'NEMOTRON_MODEL',
                 'EMBEDDING_MODEL', 'CHROMA_PERSIST_DIRECTORY'):
        if blank:
            monkeypatch.setenv(name, '')
        else:
            monkeypatch.delenv(name, raising=False)
    with patch('dotenv.load_dotenv'):
        settings = runpy.run_path(str(config.ROOT / 'backend/config.py'))
    assert settings['NEMOTRON_API_KEY'] == ''
    assert settings['NEMOTRON_BASE_URL'] == ''
    assert settings['NEMOTRON_MODEL'] == ''
    assert settings['EMBEDDING_MODEL'] == 'all-MiniLM-L6-v2'
    assert settings['CHROMA_PERSIST_DIRECTORY'] == '.cache/chroma'
    assert settings['chroma_path']() == str(config.ROOT / '.cache/chroma')


def test_environment_overrides(monkeypatch):
    overrides = {
        'NEMOTRON_BASE_URL': 'https://example.invalid/v1',
        'NEMOTRON_API_KEY': 'test-only',
        'NEMOTRON_MODEL': 'test-model',
        'EMBEDDING_MODEL': 'test-embedding',
        'CHROMA_PERSIST_DIRECTORY': '/private/tmp/test-sentinelai-chroma',
    }
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)
    with patch('dotenv.load_dotenv'):
        settings = runpy.run_path(str(config.ROOT / 'backend/config.py'))
    assert all(settings[name] == value for name, value in overrides.items())
    assert settings['chroma_path']() == overrides['CHROMA_PERSIST_DIRECTORY']
