from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# 1. Modelo da Página individual
class PageSchema(BaseModel):
    page_number: int
    image_url: str

# 2. Modelo do Capítulo (Aplicando o Subset Pattern)
class ChapterSchema(BaseModel):
    comic_id: str
    chapter_number: int
    title: str
    
    # SUBSET PATTERN: O banco entregará apenas estas páginas na primeira requisição,
    # aliviando a rede. O restante será chamado depois pelo Intersection Observer.
    initial_pages: List[PageSchema] = [] 
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 3. Modelo Principal da Obra (Motor Genérico)
class ComicSchema(BaseModel):
    title: str
    author: str
    description: str
    tags: List[str] = []
    cover_url: Optional[str] = None