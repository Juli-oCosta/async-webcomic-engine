# Arquivo: backend/main.py
from fastapi import FastAPI
from backend.database import database

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