# main.py - FastAPI application for 91CrPC system

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

# Import configuration
from config import (
    APP_NAME,
    APP_ENV,
    PORT,
    CORS_ALLOWED_ORIGINS,
    ENABLE_REQUEST_LOGS,
)
# Import database connection handling
from database import check_db_connection, close_connection
# Import your routers (adjust import path if needed)
from routes.v1 import service_master_routes
from routes.v1 import operators_list_routes
from routes.v1 import operator_service_list_routes
from routes.v1 import approval_flow_master_routes
from routes.v1 import approval_chain_routes
from routes.v1 import crpc_request_pipelines_routes
from routes.v1 import crpc_requests_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    print(f"\n{'='*60}\n🚀 Starting {APP_NAME}...\n{'='*60}")
    print(f"Environment: {APP_ENV}\n")
    try:
        check_db_connection()
        print("✅ Database connection established")
    except RuntimeError as e:
        print(f"❌ Database connection failed: {e}")
        raise
    yield
    # Shutdown actions
    print(f"\n{'='*60}\n🔌 Shutting down {APP_NAME}...\n{'='*60}")
    close_connection()
    print("✅ Database connection closed")
    print(f"👋 {APP_NAME} shutdown complete\n")

# Create FastAPI instance
app = FastAPI(
    title=f"{APP_NAME} API",
    description="Backend API for 91 CrPC Request Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging (if enabled)
if ENABLE_REQUEST_LOGS:
    @app.middleware("http")
    async def log_requests(request, call_next):
        print(f"📥 {request.method} {request.url.path}")
        response = await call_next(request)
        print(f"📤 {request.method} {request.url.path} - Status: {response.status_code}")
        return response

# Include API routers
app.include_router(service_master_routes.router)
app.include_router(operators_list_routes.router)
app.include_router(operator_service_list_routes.router)
app.include_router(approval_flow_master_routes.router)
app.include_router(crpc_requests_routes.router)
app.include_router(crpc_request_pipelines_routes.router)
app.include_router(approval_chain_routes.router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {APP_NAME}",
        "version": "1.0.0",
        "environment": APP_ENV,
        "docs": "/docs"
    }

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health():
    try:
        check_db_connection()
        return {"status": "healthy", "database": "connected"}
    except RuntimeError:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "disconnected"}
        )

# Run the app
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT or 8000,
        reload=(APP_ENV == "development"),
        log_level="info"
    )
