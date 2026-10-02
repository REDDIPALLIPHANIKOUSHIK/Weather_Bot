"""Vercel service entrypoint for the FastAPI backend.

The actual application lives in app/main.py. Keeping this tiny module at the
backend service root matches Vercel's documented FastAPI service entrypoint
shape while preserving the existing package structure.
"""
from app.main import app

__all__ = ["app"]
