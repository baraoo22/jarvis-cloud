import os
import uuid
from datetime import datetime

import requests
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker


# =========================
# Config
# =========================
app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Banco (SQLite por padrão; depois pode virar Postgres com DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jarvis.db")

# SQLite precisa desse connect_args
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

DEFAULT_SYSTEM_PROMPT = (
    "Você é JARVIS. Responda em português (Brasil). "
    "Para perguntas simples, responda curto. "
    "Para perguntas maiores, responda médio e direto ao ponto. "
    "Se faltar informação, pergunte o mínimo necessário."
)

MAX_HISTORY = int(os.getenv("MAX_HISTORY", "12"))  # últimas N mensagens


# =========================
# DB Models
# =========================
class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id = Column(String(64), primary_key=True, index=True)
    system_prompt = Column(Text, nullable=False, default=DEFAULT_SYSTEM_PROMPT)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=False)
    role = Column(String(16), nullable=False)  # "user" ou "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# =========================
# Schemas
# =========================
class Pergunta(BaseModel):
    user_id: str
    session_id: str
    texto: str


class SetPrompt(BaseModel):
    user_id: str
    system_prompt: str


class NewSessionResponse(BaseModel):
    user_id: str
    session_id: str


# =========================
# Helpers
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_settings(db, user_id: str) -> UserSettings:
    s = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not s:
        s = UserSettings(user_id=user_id, system_prompt=DEFAULT_SYSTEM_PROMPT)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def load_history(db, user_id: str, session_id: str):
    rows = (
        db.query(Message)
        .filter(Message.user_id == user_id, Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(MAX_HISTORY)
        .all()
    )
    rows.reverse()
    return [{"role": r.role, "content": r.content} for r in rows]


def save_message(db, user_id: str, session_id: str, role: str, content: str):
    m = Message(user_id=user_id, session_id=session_id, role=role, content=content)
    db.add(m)
    db.commit()


def call_groq(messages):
    if not GROQ_API_KEY:
        return {"erro": "GROQ_API_KEY não configurada no Railway (Variables)."}

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.3,
    }

    r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)

    if r.status_code != 200:
        try:
            details = r.json()
        except Exception:
            details = r.text
        return {"erro": f"Groq retornou status {r.status_code}", "detalhes": details}

    j = r.json()
    if "choices" not in j or not j["choices"]:
        return {"erro": "Resposta inesperada da Groq", "detalhes": j}

    return {"resposta": j["choices"][0]["message"]["content"]}


# =========================
# Routes
# =========================
@app.get("/")
def home():
    return {"status": "Jarvis online", "model": MODEL, "db": DATABASE_URL}


@app.post("/session/new", response_model=NewSessionResponse)
def new_session():
    # Você pode gerar user_id fixo no iPhone e guardar, mas aqui já facilita
    user_id = str(uuid.uuid4())[:12]
    session_id = str(uuid.uuid4())[:12]
    return {"user_id": user_id, "session_id": session_id}


@app.post("/settings/prompt")
def set_prompt(body: SetPrompt):
    db = SessionLocal()
    try:
        s = get_or_create_settings(db, body.user_id)
        s.system_prompt = body.system_prompt.strip()
        s.updated_at = datetime.utcnow()
        db.add(s)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@app.get("/history")
def history(user_id: str, session_id: str):
    db = SessionLocal()
    try:
        msgs = load_history(db, user_id, session_id)
        return {"user_id": user_id, "session_id": session_id, "messages": msgs}
    finally:
        db.close()


@app.post("/perguntar")
def perguntar(p: Pergunta):
    db = SessionLocal()
    try:
        settings = get_or_create_settings(db, p.user_id)

        # monta contexto
        hist = load_history(db, p.user_id, p.session_id)
        messages = [{"role": "system", "content": settings.system_prompt}] + hist + [
            {"role": "user", "content": p.texto}
        ]

        # salva pergunta
        save_message(db, p.user_id, p.session_id, "user", p.texto)

        result = call_groq(messages)

        # salva resposta
        if "resposta" in result:
            save_message(db, p.user_id, p.session_id, "assistant", result["resposta"])

        return result
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
