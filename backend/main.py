import asyncio
import logging

from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse
from pymongo.errors import DocumentTooLarge, DuplicateKeyError, PyMongoError

from backend.database import database_lifespan, ensure_chapter_index, get_database
from backend.models import ChapterCreateSchema, ChapterResponseSchema, ChapterSchema, ComicSchema

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
    responses={
        413: {"description": "Documento excede o tamanho aceito pelo MongoDB"},
        503: {"description": "MongoDB indisponível"},
    },
)
async def create_comic(comic: ComicSchema, database=Depends(get_database)):
    try:
        result = await database.get_collection("catalogs").insert_one(comic.model_dump())
    except DocumentTooLarge as exc:
        raise HTTPException(
            status_code=413, detail="Documento excede o tamanho aceito pelo MongoDB."
        ) from exc
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


@app.get(
    "/api/comics/{comic_id}",
    responses={
        404: {"description": "Obra não encontrada"},
        503: {"description": "MongoDB indisponível"},
    },
)
async def get_comic(
    comic_id: str = Path(pattern=r"^[0-9a-fA-F]{24}$"),
    database=Depends(get_database),
):
    comic = await database.get_collection("catalogs").find_one({"_id": ObjectId(comic_id)})
    if comic is None:
        raise HTTPException(status_code=404, detail="Obra não encontrada.")
    comic["id"] = str(comic.pop("_id"))
    return comic


@app.post(
    "/api/comics/{comic_id}/chapters",
    status_code=status.HTTP_201_CREATED,
    response_model=ChapterResponseSchema,
    responses={
        404: {"description": "Obra não encontrada"},
        409: {"description": "Número de capítulo já cadastrado nesta obra"},
        413: {"description": "Documento excede o tamanho aceito pelo MongoDB"},
        503: {"description": "MongoDB indisponível ou índice não preparado"},
    },
)
async def create_chapter(
    chapter: ChapterCreateSchema,
    request: Request,
    comic_id: str = Path(pattern=r"^[0-9a-fA-F]{24}$"),
    database=Depends(get_database),
):
    parent_id = ObjectId(comic_id)
    parent = await database.get_collection("catalogs").find_one({"_id": parent_id}, {"_id": 1})
    if parent is None:
        raise HTTPException(status_code=404, detail="Obra não encontrada.")

    await ensure_chapter_index(request, database)
    document = ChapterSchema(comic_id=str(parent_id), **chapter.model_dump())
    try:
        result = await database.get_collection("chapters").insert_one(document.model_dump())
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Número de capítulo já cadastrado nesta obra.") from exc
    except DocumentTooLarge as exc:
        raise HTTPException(status_code=413, detail="Documento excede o tamanho aceito pelo MongoDB.") from exc
    return ChapterResponseSchema(id=str(result.inserted_id), **document.model_dump())
