"""Plan My Day — FastAPI entry point.

Run from the repo root:

    python -m app.main            # http://127.0.0.1:8000

A single-user local tool: it binds to loopback and has no auth layer, so don't
put it on a public interface without adding one.
"""

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import config
from app.api import router

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = FastAPI(title='Plan My Day', version='2.0.0')
app.include_router(router)


@app.get('/')
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / 'index.html')


@app.get('/health')
def health() -> dict[str, object]:
    return {'ok': True, 'model': config.MODEL, 'api_key_set': config.api_key_present()}


def main() -> None:
    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == '__main__':
    main()
