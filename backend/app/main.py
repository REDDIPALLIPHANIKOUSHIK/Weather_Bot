import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import chat_router, voice_router
from .services import WeatherService

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("weatherwise")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Weatherwise advisory platform backend...")
    yield
    logger.info("Shutting down Weatherwise backend...")


app = FastAPI(
    title="Weatherwise API",
    description="Deterministic weather-advisory platform for outdoor activities",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup
origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allowed_origins = [o.strip() for o in origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Weatherwise",
        "version": "1.0.0",
    }

# Register routers
app.include_router(chat_router)
app.include_router(voice_router)
