from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Pergunta(BaseModel):
    texto: str

@app.get("/")
def home():
    return {"status": "Jarvis online"}

@app.post("/perguntar")
def perguntar(p: Pergunta):
    pergunta = p.texto.lower()

    if "hora" in pergunta:
        from datetime import datetime
        agora = datetime.now().strftime("%H:%M")
        return {"resposta": f"São {agora}."}

    return {"resposta": "Servidor funcionando. IA será conectada na próxima etapa."}
