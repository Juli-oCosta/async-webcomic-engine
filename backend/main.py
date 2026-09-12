# Arquivo: backend/main.py
from fastapi import FastAPI
from backend.database import database
from fastapi import status
from backend.models import ComicSchema
from backend.database import comic_collection

# Inicializa o aplicativo FastAPI
app = FastAPI(title="Engine de Webcomics", description="API Assíncrona para o TGI")

# Rota raiz só para testar se o servidor está de pé
@app.get("/")
async def root():
    return {"mensagem": "Aopa! Servidor FastAPI rodando."}

# Rota de status para validar a resposta
@app.get("/api/status")
async def status_check():
    return {"status": "Tudo verde por aqui, arquitetura pronta pro combate!"}

# Nova rota para testar o pulso do banco de dados
@app.get("/api/db-check")
async def ping_database():
    try:
        # Envia um comando "ping" oficial para o Mongo
        await database.command("ping")
        return {"status": "Conexão assíncrona com o MongoDB estabelecida!"}
    except Exception as e:
        return {"erro": f"Falha ao conectar no banco: {str(e)}"}
    
# Rota POST para criar uma nova Webcomic no motor genérico
@app.post("/api/comics", status_code=status.HTTP_201_CREATED)
async def create_comic(comic: ComicSchema):
    # Converte o molde validado pelo Pydantic em um dicionário que o Mongo entende
    comic_dict = comic.model_dump() 
    
    # Executa a inserção de forma assíncrona no banco
    result = await comic_collection.insert_one(comic_dict)
    
    # Retorna o ID único gerado pelo MongoDB e uma mensagem de sucesso
    return {
        "id": str(result.inserted_id), 
        "mensagem": f"A obra '{comic.title}' foi registrada com sucesso na arquitetura!"
    }

# Rota GET para listar todas as obras cadastradas no motor
@app.get("/api/comics")
async def list_comics():
    # Inicia a busca no banco (limitamos a 100 para não engasgar a memória em testes futuros)
    cursor = comic_collection.find({}).limit(100)
    comics = await cursor.to_list(length=100)
    
    # O MongoDB gera o _id em um formato binário especial (ObjectId).
    # Precisamos converter isso para texto comum (string) para o FastAPI conseguir gerar o JSON.
    for comic in comics:
        comic["id"] = str(comic["_id"])
        del comic["_id"]
        
    return comics