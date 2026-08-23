# Arquivo: backend/main.py
from fastapi import FastAPI

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