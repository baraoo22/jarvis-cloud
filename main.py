import os
import requests
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class Pergunta(BaseModel):
    texto: str

@app.get("/")
def root():
    return {"status": "Jarvis online 🚀"}

@app.post("/perguntar")
def perguntar(pergunta: Pergunta):

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        # 🔥 MODELO ATUAL FUNCIONANDO
        "model": "llama-3.1-8b-instant",
        "messages": [
            {
                "role": "system",
                "content": "Você é JARVIS, assistente inteligente, objetivo e direto."
            },
            {
                "role": "user",
                "content": pergunta.texto
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    # 🔎 Se der erro, mostrar o erro real
    if response.status_code != 200:
        return {
            "error": f"Groq retornou status {response.status_code}",
            "details": response.json()
        }

    resposta = response.json()["choices"][0]["message"]["content"]

    return {"resposta": resposta}
