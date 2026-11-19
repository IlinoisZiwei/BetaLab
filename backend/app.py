"""Application assembly: middleware, errors, health and business/compute routers."""
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .database import database
from .auth import current_session
from .routes import accounts, catalog, videos
from .compute.api import create_router

app = FastAPI(title='BetaLab API', version='0.1.0')
ORIGINS = set(os.getenv('APP_ORIGINS', 'http://localhost:8443,http://127.0.0.1:8443').split(','))

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={'error': {'message': str(exc.detail)}}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Do not echo input values (especially passwords).
    return JSONResponse(status_code=422, content={'error': {'message': 'Invalid request fields'}})


@app.middleware('http')
async def csrf_origin(request: Request, call_next):
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        # Explicit browser origin allowlist: no trusting client-controlled Host.
        if request.headers.get('origin') not in ORIGINS:
            return JSONResponse(status_code=403, content={'error': {'message': 'Origin not allowed'}})
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/health')
def health():
    with database() as db:
        db.execute('SELECT 1')
    return {'ready': True}


app.include_router(accounts.router)
app.include_router(catalog.router)
app.include_router(videos.router)
app.include_router(create_router(current_session))
