"""Opt-in only: real inference through the user's existing SSH tunnel.

NEMOTRON_RUN_LIVE=1 python -m pytest backend/tests/test_nemotron_live.py -q
This calls chat_json directly; fallback cannot make this test pass.
"""
import os
import uuid

import pytest

from backend import config
from backend.llm.nemotron_client import NemotronClient

pytestmark = pytest.mark.skipif(os.getenv('NEMOTRON_RUN_LIVE') != '1',
                                reason='Real Nemotron calls require explicit opt-in')


def test_real_nemotron_json_response():
    assert config.NEMOTRON_BASE_URL, 'Set NEMOTRON_BASE_URL to your forwarded endpoint'
    assert config.NEMOTRON_MODEL, 'Set NEMOTRON_MODEL to the deployed model ID'
    assert config.NEMOTRON_API_KEY, 'Empty key selects fallback; use local-vllm for the unauthenticated tunnel'
    nonce = uuid.uuid4().hex
    result = NemotronClient().chat_json(
        'You are a connectivity probe. Respond only with the requested JSON object.',
        'Return exactly this JSON object: {"connection": "ok", "nonce": "' + nonce + '"}',
        {},
    )
    assert result == {'connection': 'ok', 'nonce': nonce}
