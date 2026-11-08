"""Reviewer-triggered inference checks; no automatic model calls on page load."""
from datetime import datetime, timezone
from time import monotonic
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from backend import config
from backend.llm.nemotron_client import NemotronClient, LLMUnavailable
from backend.security.auth import require_role
from backend.security.audit import write_audit_event

router = APIRouter(prefix='/api/ai', tags=['ai'])
Reviewer = Annotated[dict, Depends(require_role('reviewer'))]


@router.post('/check')
def check_nemotron(user: Reviewer):
    started = monotonic()
    nonce = uuid.uuid4().hex
    verified = False
    mode = 'fallback'
    message = 'No API key configured. Source-only fallback is active.'
    if config.NEMOTRON_API_KEY:
        try:
            result = NemotronClient().chat_json(
                'You are a connectivity probe. Return only the exact requested JSON.',
                'Return exactly {"status":"ok","nonce":"' + nonce + '"}', {})
            verified = result == {'status': 'ok', 'nonce': nonce}
            mode = 'nemotron' if verified else 'unavailable'
            message = 'Live JSON inference verified.' if verified else 'The model response did not pass verification.'
        except LLMUnavailable:
            mode = 'unavailable'
            message = 'Inference unavailable. Check the SSH tunnel, model settings, and server JSON support.'
    write_audit_event(None, 'user', user['user_id'], 'nemotron_connection_check',
                      'model', config.NEMOTRON_MODEL or None, {'status': mode})
    return {'verified': verified, 'mode': mode, 'message': message,
            'model': config.NEMOTRON_MODEL or None,
            'latency_ms': round((monotonic() - started) * 1000),
            'checked_at': datetime.now(timezone.utc).isoformat()}
