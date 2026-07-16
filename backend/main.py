from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from tft_synergies_live import ASSETS_DIR

from .schemas import AuthStatusResponse, BootstrapResponse, LoginRequest, MetaResponse, SearchRequest, SearchResponse, TraitsResponse, UnitsResponse
from .cache import clear_cache, get_cache_stats
from .service import get_bootstrap, get_meta, get_traits, get_units, search, search_compact, warm_up_cache

AUTH_COOKIE_NAME = "tft_admin_session"
AUTH_USERNAME = "admin"
AUTH_PASSWORD = "tftAbc123@"
AUTH_SIGNING_SECRET = "tft-perfect-auth-v1"


app = FastAPI(
    title="TFT Perfect Synergies API",
    version="0.1.0",
    description="Backend API for TFT team search based on the local perfect synergies engine.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


def _issue_auth_token(username: str) -> str:
    digest = hmac.new(
        AUTH_SIGNING_SECRET.encode("utf-8"),
        msg=username.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"{username}:{digest}"


def _is_authenticated(request: Request) -> bool:
    raw = request.cookies.get(AUTH_COOKIE_NAME)
    if not raw or ":" not in raw:
        return False
    username, supplied_sig = raw.split(":", 1)
    if username != AUTH_USERNAME:
        return False
    expected_sig = _issue_auth_token(username).split(":", 1)[1]
    return hmac.compare_digest(supplied_sig, expected_sig)


@app.middleware("http")
async def add_debug_headers(request: Request, call_next):
    protected_api = request.url.path.startswith("/api/") and not request.url.path.startswith("/api/auth/")
    if protected_api and not _is_authenticated(request):
        response = Response(status_code=401, content='{"detail":"Authentication required"}', media_type="application/json")
        response.headers["X-Cache"] = "NONE"
        response.headers["X-Cache-Hits"] = "0"
        response.headers["X-Cache-Misses"] = "0"
        response.headers["X-Process-Time-Ms"] = "0.00"
        return response
    before = get_cache_stats()
    started = time.perf_counter()
    response: Response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    after = get_cache_stats()
    hit_delta = after["hits"] - before["hits"]
    miss_delta = after["misses"] - before["misses"]
    response.headers["X-Cache-Hits"] = str(hit_delta)
    response.headers["X-Cache-Misses"] = str(miss_delta)
    if hit_delta > 0:
        response.headers["X-Cache"] = "HIT"
    elif miss_delta > 0:
        response.headers["X-Cache"] = "MISS"
    else:
        response.headers["X-Cache"] = "NONE"
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    return response


@app.on_event("startup")
def app_startup() -> None:
    threading.Thread(target=warm_up_cache, name="cache-warmup", daemon=True).start()


@app.get("/api/auth/me", response_model=AuthStatusResponse)
def auth_me(request: Request) -> dict:
    if _is_authenticated(request):
        return {"authenticated": True, "username": AUTH_USERNAME}
    return {"authenticated": False, "username": None}


@app.post("/api/auth/login", response_model=AuthStatusResponse)
def auth_login(payload: LoginRequest, request: Request) -> Response:
    if payload.username != AUTH_USERNAME or payload.password != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response = Response(
        content='{"authenticated":true,"username":"admin"}',
        media_type="application/json",
    )
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=_issue_auth_token(AUTH_USERNAME),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return response


@app.post("/api/auth/logout", response_model=AuthStatusResponse)
def auth_logout() -> Response:
    response = Response(content='{"authenticated":false,"username":null}', media_type="application/json")
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "cache": get_cache_stats()}


@app.get("/api/cache")
def cache_stats() -> dict:
    return get_cache_stats()


@app.post("/api/cache/clear")
def cache_clear() -> dict:
    clear_cache()
    return {"status": "cleared", "cache": get_cache_stats()}


@app.get("/api/meta", response_model=MetaResponse)
def meta(set_number: str = Query(default="17"), refresh: bool = Query(default=False)) -> dict:
    try:
        return {"meta": get_meta(set_number=set_number, refresh=refresh)}
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.get("/api/bootstrap", response_model=BootstrapResponse)
def bootstrap(set_number: str = Query(default="17"), refresh: bool = Query(default=False)) -> dict:
    try:
        return get_bootstrap(set_number=set_number, refresh=refresh)
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.get("/api/units", response_model=UnitsResponse)
def units(set_number: str = Query(default="17"), refresh: bool = Query(default=False)) -> dict:
    try:
        return get_units(set_number=set_number, refresh=refresh)
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.get("/api/traits", response_model=TraitsResponse)
def traits(set_number: str = Query(default="17"), refresh: bool = Query(default=False)) -> dict:
    try:
        return get_traits(set_number=set_number, refresh=refresh)
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.post("/api/search", response_model=SearchResponse)
def run_search(request: SearchRequest) -> dict:
    try:
        return search(request)
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@app.get("/api/perfect-synergies/{set_number}/{max_unused_traits}/{level}/{mode}")
def perfect_synergies_compat(
    set_number: str,
    max_unused_traits: int,
    level: int,
    mode: str,
    limit: int = Query(default=100, ge=1, le=500),
    refresh: bool = Query(default=False),
) -> list:
    try:
        return search_compact(
            set_number=set_number,
            max_unused_traits=max_unused_traits,
            level=level,
            mode=mode,
            limit=limit,
            refresh=refresh,
        )
    except Exception as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
