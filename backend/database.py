from contextlib import asynccontextmanager
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from motor.motor_asyncio import AsyncIOMotorClient


@asynccontextmanager
async def database_lifespan(app: FastAPI):
    # Um cliente por aplicação, compartilhado entre requisições e fechado ao sair.
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    client = AsyncIOMotorClient(
        os.getenv("MONGO_URL", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
        waitQueueTimeoutMS=5000,
        timeoutMS=5000,
        tz_aware=True,
    )
    try:
        database = client[os.getenv("MONGO_DB_NAME", "webcomics_db")]
        app.state.database = database
        # Selecionar uma coleção não a cria: isso ocorre na primeira gravação.
        app.state.comic_collection = database.get_collection("catalogs")
        app.state.chapters_collection = database.get_collection("chapters")
        app.state.pages_collection = database.get_collection("pages")
        yield
    finally:
        client.close()


def get_database(request: Request):
    """Dependência das rotas; pode ser substituída nos testes."""
    return request.app.state.database
