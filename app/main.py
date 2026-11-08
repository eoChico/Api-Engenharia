from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth, health, products, tables, users
from app.core.config import settings
from app.core.limiter import limiter
from app.core.middleware import SecurityHeadersMiddleware
from app.db.session import engine

is_prod = settings.ENVIRONMENT == "prod"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)

async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    retry_after = 60  # padrão, se não der para saber a janela
    if isinstance(exc, RateLimitExceeded) and exc.limit is not None:
        retry_after = exc.limit.limit.GRANULARITY.seconds
    return JSONResponse(
        status_code=429,
        content={"detail": "Muitas requisições. Tente novamente em instantes."},
        headers={"Retry-After": str(retry_after)},
    )

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# O ÚLTIMO adicionado é o mais externo. CORS fica por fora para que até
# respostas de erro (401, 429, 500) carreguem os headers CORS.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,  # Bearer no header não precisa de credentials
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(products.router, prefix='/api/v1')
app.include_router(tables.router, prefix='/api/v1')
app.include_router(users.router, prefix="/api/v1")
