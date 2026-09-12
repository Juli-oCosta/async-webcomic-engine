import asyncio
import logging

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from backend.database import database_lifespan, get_database
from backend.models import ComicSchema

logger = logging.getLogger(__name__)
DB_CHECK_TIMEOUT_SECONDS = 5

app = FastAPI(
    title="Engine de Webcomics",
    description="API Assíncrona para o TGI",
    lifespan=database_lifespan,
)


@app.exception_handler(PyMongoError)
async def handle_database_error(request: Request, exc: PyMongoError):
    logger.warning("Operação MongoDB falhou: %s", type(exc).__name__)
    return JSONResponse(
        status_code=503, content={"detail": "MongoDB temporariamente indisponível."}
    )


@app.get("/")
async def root():
    return {"mensagem": "Aopa! Servidor FastAPI rodando."}


@app.get("/api/status")
async def status_check():
    # Liveness: o processo responde, mesmo se o banco estiver indisponível.
    return {"status": "Tudo verde por aqui, arquitetura pronta pro combate!"}


@app.get("/api/db-check", responses={503: {"description": "MongoDB indisponível"}})
async def ping_database(database=Depends(get_database)):
    try:
        await asyncio.wait_for(database.command("ping"), timeout=DB_CHECK_TIMEOUT_SECONDS)
    except (PyMongoError, asyncio.TimeoutError) as exc:
        # Não incluir credenciais ou detalhes da conexão na resposta pública.
        logger.warning("Verificação do MongoDB falhou: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="MongoDB temporariamente indisponível.") from exc
    return {"status": "Conexão assíncrona com o MongoDB estabelecida!"}


@app.post(
    "/api/comics", status_code=status.HTTP_201_CREATED,
    responses={503: {"description": "MongoDB indisponível"}},
)
async def create_comic(comic: ComicSchema, database=Depends(get_database)):
    result = await database.get_collection("catalogs").insert_one(comic.model_dump())
    return {
        "id": str(result.inserted_id),
        "mensagem": f"A obra '{comic.title}' foi registrada com sucesso na arquitetura!",
    }


@app.get("/api/comics", responses={503: {"description": "MongoDB indisponível"}})
async def list_comics(
    limit: int = Query(default=100, ge=1, le=100),
    after: str | None = Query(default=None, pattern=r"^[0-9a-fA-F]{24}$"),
    database=Depends(get_database),
):
    # O cursor usa o índice nativo de _id; evita percorrer páginas com skip.
    query = {"_id": {"$gt": ObjectId(after)}} if after is not None else {}
    cursor = database.get_collection("catalogs").find(query).sort("_id", 1).limit(limit)
    comics = await cursor.to_list(length=limit)
    for comic in comics:
        comic["id"] = str(comic.pop("_id"))
    return comics
