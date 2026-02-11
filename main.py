import os
import requests
import sqlite3
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ===== CONFIG FIXA =====
USER_ID = "jarvis_user"
SESSION_ID = "jarvis_session"

# ===== BANCO DE DADOS =====
conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    session_id TEXT,
    role TEXT,
    content TEXT
)
""")
conn.commit()

# ===== MODELO DE ENTRADA =====
class Pergunta(BaseModel):
    texto: str

# ===== ROOT =====
@app.get("/")
def root():
    return {"status": "Jarvis online"}

# ===== PERGUNTAR =====
@app.post("/perguntar")
def perguntar(pergunta: Pergunta):

    # Salva pergunta
    cursor.execute(
        "INSERT INTO messages (user_id, session_id, role, content) VALUES (?, ?, ?, ?)",
        (USER_ID, SESSION_ID, "user", pergunta.texto)
    )
    conn.commit()

    # Busca histórico
    cursor.execute(
        "SELECT role, content FROM messages WHERE user_id=? AND session_id=? ORDER BY id ASC",
        (USER_ID, SESSION_ID)
    )
    historico = cursor.fetchall()

    mensagens = [
        {"role": "system", "content": "Você é Jarvis, assistente pessoal inteligente e útil."}
    ]

    for role, content in historico:
        mensagens.append({"role": role, "content": content})

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.1-8b-instant",
        "messages": mensagens
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=data
    )

    resposta_json = response.json()

    if "choices" not in resposta_json:
        return {"erro": resposta_json}

    resposta = resposta_json["choices"][0]["message"]["content"]

    # Salva resposta
    cursor.execute(
        "INSERT INTO messages (user_id, session_id, role, content) VALUES (?, ?, ?, ?)",
        (USER_ID, SESSION_ID, "assistant", resposta)
    )
    conn.commit()

    return {"resposta": resposta}
