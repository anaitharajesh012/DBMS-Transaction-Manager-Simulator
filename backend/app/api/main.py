"""
main.py - FastAPI Application Entrypoint.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router, ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Capture current asyncio loop for thread-safe WebSocket broadcasts
    loop = asyncio.get_running_loop()
    ws_manager.set_loop(loop)
    yield


app = FastAPI(
    title="Database Transaction Manager Simulator API",
    description="Educational simulator demonstrating transaction management, WAL, locking, deadlock detection, and recovery from first principles.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local React development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {
        "system": "Database Transaction Manager Simulator",
        "status": "ONLINE",
        "docs": "/docs",
        "websocket": "/api/ws",
    }
