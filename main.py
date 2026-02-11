import os
import requests
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Pergunta(BaseModel):
    texto: str

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")

SYSTEM_PROMPT = (
    "Você é JARVIS. Responda em português (Brasil). "
    "Para perguntas simples, responda curto. "
    "Para perguntas maiores, responda médio e direto ao ponto. "
    "Se faltar informação, pergunte o mínimo necessário."
)

@app.get("/")
def home():
    return {"status": "Jarvis online", "model": MODEL}

@app.get("/health")
def health():
    return {
        "ok": True,
        "has_key": bool(GROQ_API_KEY),
        "model": MODEL,
    }

@app.post("/perguntar")
def perguntar(p: Pergunta):
    # 1) Chave não configurada
    if not GROQ_API_KEY:
        return {
            "erro": "GROQ_API_KEY não configurada no Railway (Variables).",
            "como_corrigir": "Railway > Service > Variables > New Variable > GROQ_API_KEY = sua chave gsk_...",
        }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": p.texto},
        ],
        "temperature": 0.3,
    }

    try:
        r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)

        # 2) Se Groq retornar erro, mostramos o corpo
        if r.status_code != 200:
            # tenta JSON, senão devolve texto cru
            try:
                details = r.json()
            except Exception:
                details = r.text

            return {
                "erro": f"Groq retornou status {r.status_code}",
                "detalhes": details,
            }

        # 3) Formato esperado
        j = r.json()
        if "choices" not in j or not j["choices"]:
            return {
                "erro": "Resposta inesperada da Groq (sem 'choices').",
                "detalhes": j,
            }

        content = j["choices"][0]["message"]["content"]
        return {"resposta": content}

    except requests.exceptions.Timeout:
        return {"erro": "Timeout chamando a Groq (demorou demais). Tente novamente."}

    except Exception as e:
        return {"erro": "Falha ao chamar a Groq", "detalhes": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
