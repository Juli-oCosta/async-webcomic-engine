from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import unquote, urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, computed_field, field_validator

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


class ChapterSummarySchema(ChapterCreateSchema):
    """Metadados do capítulo, sem copiar a lista de páginas para a listagem."""
    id: Text
    comic_id: Text
    created_at: AwareDatetime

    @computed_field
    @property
    def chapter_number_text(self) -> str:
        """Texto decimal exato para clientes que usam Number de JavaScript."""
        return str(self.chapter_number)


class PageCreateSchema(DomainSchema):
    page_number: int = Field(ge=1, le=2**63 - 1, strict=True)
    image_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]
    width: int = Field(ge=1, le=20000, strict=True)
    height: int = Field(ge=1, le=20000, strict=True)

    @field_validator("image_url")
    @classmethod
    def validate_image_reference(cls, value):
        if any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
            raise ValueError("Referência de imagem inválida.")
        parsed = urlsplit(value)
        local = not parsed.scheme and not parsed.netloc and parsed.path.startswith("/static/")
        remote = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password
        if not (local or remote) or ".." in unquote(parsed.path).split("/"):
            raise ValueError("Use /static/... ou uma URL HTTP(S) de imagem.")
        return value


class PageResponseSchema(PageCreateSchema):
    id: Text
    chapter_id: Text

    @computed_field
    @property
    def page_number_text(self) -> str:
        return str(self.page_number)


class ComicSchema(DomainSchema):
    title: Text
    author: Text
    description: str
    tags: list[Text] = Field(default_factory=list)
    cover_url: MediaReference | None = None
