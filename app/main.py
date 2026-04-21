from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.payments import router as payments_router
from app.core.config import settings
from app.db.session import init_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="Payment Processing Service",
        description="Async microservice for payment processing with webhook notifications",
        version="1.0.0",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(payments_router, prefix="/api/v1")

    @app.on_event("startup")
    async def startup():
        await init_db()

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app


app = create_app()
