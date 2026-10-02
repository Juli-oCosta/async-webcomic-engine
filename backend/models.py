from datetime import datetime, timezone
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
MediaReference = Text


class DomainSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class PageSchema(DomainSchema):
    page_number: int = Field(ge=1, strict=True)
    # Referência textual: aceita URL ou caminho relativo do storage.
    image_url: MediaReference


class PageDocumentSchema(PageSchema):
    """Documento da coleção pages, vinculado ao capítulo."""
    chapter_id: Text


class ChapterCreateSchema(DomainSchema):
    # Inteiro positivo compatível com o int64 do BSON.
    chapter_number: int = Field(ge=1, le=2**63 - 1, strict=True)
    title: Text


class ChapterSchema(ChapterCreateSchema):
    comic_id: Text
    # A quantidade do subconjunto será definida junto das rotas de capítulos.
    initial_pages: list[PageSchema] = Field(default_factory=list)
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChapterResponseSchema(ChapterSchema):
    id: Text


class ComicSchema(DomainSchema):
    title: Text
    author: Text
    description: str
    tags: list[Text] = Field(default_factory=list)
    cover_url: MediaReference | None = None
