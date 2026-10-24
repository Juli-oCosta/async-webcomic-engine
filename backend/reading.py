"""Contratos de leitura limitados, separados dos cadastros já existentes."""
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pymongo.errors import DocumentTooLarge, DuplicateKeyError

from backend.database import ensure_page_index, get_database
from backend.models import ChapterSummarySchema, PageCreateSchema, PageResponseSchema

router = APIRouter(prefix="/api")
OBJECT_ID_PATTERN = r"^[0-9a-fA-F]{24}$"
MAX_NUMBER = 2**63 - 1


@router.get(
    "/comics/{comic_id}/chapters",
    response_model=list[ChapterSummarySchema],
    responses={404: {"description": "Obra não encontrada"}, 503: {"description": "MongoDB indisponível"}},
)
async def list_chapters(
    comic_id: str = Path(pattern=OBJECT_ID_PATTERN),
    limit: int = Query(default=20, ge=1, le=100),
    after: int = Query(default=0, ge=0, le=MAX_NUMBER),
    database=Depends(get_database),
):
    parent_id = ObjectId(comic_id)
    parent = await database.get_collection("catalogs").find_one({"_id": parent_id}, {"_id": 1})
    if parent is None:
        raise HTTPException(status_code=404, detail="Obra não encontrada.")
    # A numeração é única por obra; o cursor acompanha a ordem de leitura.
    query = {"comic_id": str(parent_id), "chapter_number": {"$gt": after}}
    projection = {"initial_pages": 0}
    cursor = database.get_collection("chapters").find(query, projection).sort("chapter_number", 1).limit(limit)
    chapters = await cursor.to_list(length=limit)
    for chapter in chapters:
        chapter["id"] = str(chapter.pop("_id"))
    return chapters


async def require_chapter(chapter_id, database):
    parent_id = ObjectId(chapter_id)
    parent = await database.get_collection("chapters").find_one({"_id": parent_id}, {"_id": 1})
    if parent is None:
        raise HTTPException(status_code=404, detail="Capítulo não encontrado.")
    return str(parent_id)


@router.post(
    "/chapters/{chapter_id}/pages",
    status_code=status.HTTP_201_CREATED,
    response_model=PageResponseSchema,
    responses={
        404: {"description": "Capítulo não encontrado"},
        409: {"description": "Número de página repetido no capítulo"},
        413: {"description": "Documento grande demais"},
        503: {"description": "MongoDB indisponível ou índice não preparado"},
    },
)
async def create_page(
    page: PageCreateSchema,
    request: Request,
    chapter_id: str = Path(pattern=OBJECT_ID_PATTERN),
    database=Depends(get_database),
):
    canonical_id = await require_chapter(chapter_id, database)
    await ensure_page_index(request, database)
    document = {**page.model_dump(), "chapter_id": canonical_id}
    try:
        result = await database.get_collection("pages").insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Número de página já cadastrado neste capítulo.") from exc
    except DocumentTooLarge as exc:
        raise HTTPException(status_code=413, detail="Documento excede o tamanho aceito pelo MongoDB.") from exc
    # O driver pode acrescentar _id ao dicionário usado na gravação.
    return PageResponseSchema(id=str(result.inserted_id), chapter_id=canonical_id, **page.model_dump())


@router.get(
    "/chapters/{chapter_id}/pages",
    response_model=list[PageResponseSchema],
    responses={404: {"description": "Capítulo não encontrado"}, 503: {"description": "MongoDB indisponível"}},
)
async def list_pages(
    chapter_id: str = Path(pattern=OBJECT_ID_PATTERN),
    limit: int = Query(default=20, ge=1, le=100),
    after: int = Query(default=0, ge=0, le=MAX_NUMBER),
    database=Depends(get_database),
):
    canonical_id = await require_chapter(chapter_id, database)
    query = {"chapter_id": canonical_id, "page_number": {"$gt": after}}
    cursor = database.get_collection("pages").find(query).sort("page_number", 1).limit(limit)
    pages = await cursor.to_list(length=limit)
    for page in pages:
        page["id"] = str(page.pop("_id"))
    return pages
