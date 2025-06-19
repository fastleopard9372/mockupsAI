from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from app.config.settings import settings
from app.config.database import init_db
from app.core.exceptions import CustomException
from app.api.v1 import auth, users, mockups, products, credits, subscriptions, payments, admin


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up AI Mockup Platform backend...")
    await init_db()
    logger.info("Database initialized successfully")

    yield
    
    # Shutdown
    logger.info("Shutting down AI Mockup Platform backend...")



# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered promotional product mockup platform",
    openapi_url="/api/v1/openapi.json" if settings.DEBUG else None,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,  # Use lifespan instead of on_event
    swagger_ui_parameters={
        "deepLinking": True,
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
        "syntaxHighlight.theme": "monokai",
    },
    openapi_tags=[
        {"name": "Authentication", "description": "Authentication endpoints"},
        {"name": "Users", "description": "Users endpoints"},
        {"name": "Mockups", "description": "Mockups endpoints"},
        {"name": "Products", "description": "Products endpoints"},
        {"name": "Credits", "description": "Credits endpoints"},
        {"name": "Subscriptions", "description": "Subscriptions endpoints"},
        {"name": "Payments", "description": "Payments endpoints with i18n support"},
        {"name": "Admin", "description": "Admin endpoints"}            
    ],
    contact={
        "name": "API Support",
        "email": "support@example.com",
        "url": "https://example.com/support",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handlers
@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


# API Routes
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])
app.include_router(mockups.router, prefix="/api/v1", tags=["Mockups"])
app.include_router(products.router, prefix="/api/v1", tags=["Products"])
app.include_router(credits.router, prefix="/api/v1", tags=["Credits"])
app.include_router(subscriptions.router, prefix="/api/v1", tags=["Subscriptions"])
app.include_router(payments.router, prefix="/api/v1", tags=["Payments"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


# Root endpoint
@app.get("/")
async def root():               
    return {
        "message": "Welcome to AI Mockup Platform API",
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None
    }