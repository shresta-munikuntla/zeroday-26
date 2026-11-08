"""Isolated real-agent API for browser tests; no production database writes."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import uvicorn


def main():
    with TemporaryDirectory(prefix='sentinel-browser-') as folder:
        os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(folder) / 'agents.db')
        os.environ['DATABASE_PATH'] = str(Path(folder) / 'app.sqlite3')
        os.environ['NEMOTRON_API_KEY'] = ''
        os.environ['NOTIFICATION_MODE'] = 'mock'
        uvicorn.run('backend.main:app', host='127.0.0.1',
                    port=int(os.getenv('SENTINEL_E2E_PORT', '8003')), log_level='warning')


if __name__ == '__main__':
    main()
