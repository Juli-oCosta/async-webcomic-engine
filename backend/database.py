# Arquivo: backend/database.py
from motor.motor_asyncio import AsyncIOMotorClient

# URL de conexão padrão para o MongoDB rodando localmente
MONGO_URL = "mongodb://localhost:27017"

# Cria o "cliente" assíncrono que vai gerenciar a comunicação
client = AsyncIOMotorClient(MONGO_URL)

# Seleciona o banco de dados (se não existir, o Mongo cria automaticamente no primeiro insert)
database = client.webcomics_db

# Seleciona a "tabela" (coleção) onde guardaremos a estrutura das páginas
comic_collection = database.get_collection("catalogs")