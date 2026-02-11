import os
import requests
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Pergunta(BaseModel):
    texto: str

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

@app.get("/")
def home():
    return {"status": "Jarvis online"}

@app.post("/perguntar")
def perguntar(p: Pergunta):

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama3-8b-8192",
        "messages": [
            {
                "role": "system",
                "content": "Você é JARVIS, assistente pessoal inteligente, responde de forma clara, objetiva e natural."
            },
            {
                "role": "user",
                "content": p.texto
            }
        ]
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=data
    )

    resposta = response.json()["choices"][0]["message"]["content"]

    return {"resposta": resposta}

