"""Shared configuration with offline development defaults.

The local persistence default is user-authorized, not taken from the missing
specification. Brev endpoint identifiers stay empty until supplied.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
NEMOTRON_BASE_URL = os.getenv('NEMOTRON_BASE_URL', '')
NEMOTRON_API_KEY = os.getenv('NEMOTRON_API_KEY', '')
NEMOTRON_MODEL = os.getenv('NEMOTRON_MODEL', '')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL') or 'all-MiniLM-L6-v2'
# .cache/ is already ignored by the repository. Blank .env.example values also
# select this development default, so copying that file doesn't break ingestion.
CHROMA_PERSIST_DIRECTORY = os.getenv('CHROMA_PERSIST_DIRECTORY') or '.cache/chroma'


def chroma_path() -> str:
    if not CHROMA_PERSIST_DIRECTORY:
        raise ValueError('CHROMA_PERSIST_DIRECTORY must be configured')
    return str((ROOT / CHROMA_PERSIST_DIRECTORY).resolve())
