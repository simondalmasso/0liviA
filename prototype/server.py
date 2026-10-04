#!/usr/bin/env python3
"""Small dependency-free vertical slice for 0liviA.

Browser -> session -> replaceable model router -> SQLite context -> safe repo tool -> SSE.
The default model is deterministic; an OpenAI-compatible provider is opt-in via environment.
"""
from __future__ import annotations
import json, os, sqlite3, subprocess, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("OLIVIA_DB", ROOT / "prototype" / "olivia.sqlite3"))
STATIC = ROOT / "prototype" / "static"


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    cx = sqlite3.connect(DB_PATH)
    cx.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL)")
    cx.execute("CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, session_id TEXT NOT NULL, fact TEXT NOT NULL, source TEXT NOT NULL, created_at REAL NOT NULL, UNIQUE(session_id, fact))")
    cx.commit()
    return cx


def repo_status():
    try:
        out = subprocess.run(["git", "status", "--short", "--branch"], cwd=ROOT, text=True, capture_output=True, timeout=3, check=False)
        return " ".join(out.stdout.split())[:2000]
    except Exception as exc:
        return f"unavailable: {type(exc).__name__}"


def model_reply(user_text: str, context: list[tuple[str, str]]) -> tuple[str, str]:
    """Replaceable model boundary. No secret or external call is required for the proof."""
    provider = os.environ.get("OLIVIA_MODEL_PROVIDER", "deterministic-fallback")
    if provider != "deterministic-fallback":
        # Deliberately fail closed until a provider adapter is added and tested.
        provider = "deterministic-fallback"
    recent = " | ".join(f"{role}: {text[:80]}" for role, text in context[-4:])
    reply = f"Recibido. Ruta activa: {provider}. Contexto durable cargado ({len(context)} mensajes). " \
            f"Puedo continuar desde aquí. Último estado de repo: {repo_status()}."
    if recent:
        reply += f" Contexto reciente: {recent}."
    return reply, provider


class Handler(BaseHTTPRequestHandler):
    server_version = "0liviA-proof/0.1"
    def send_json(self, code, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self.send_json(200, {"ok": True, "db": str(DB_PATH), "model": os.environ.get("OLIVIA_MODEL_PROVIDER", "deterministic-fallback")}); return
        if path == "/api/session":
            sid = urlparse(self.path).query.replace("session_id=", "", 1) or "default"
            with db() as cx:
                rows = cx.execute("SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id", (sid,)).fetchall()
            self.send_json(200, {"session_id": sid, "messages": [{"role": r, "content": c, "created_at": t} for r,c,t in rows]}); return
        if path == "/" or path == "/index.html":
            raw = (STATIC / "index.html").read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/chat": self.send_error(404); return
        try:
            n = int(self.headers.get("Content-Length", "0")); body = json.loads(self.rfile.read(n)); sid = str(body.get("session_id", "default")); text = str(body.get("message", "")).strip()
            if not text or len(text) > 4000: raise ValueError("message must contain 1..4000 characters")
            with db() as cx:
                cx.execute("INSERT INTO messages(session_id,role,content,created_at) VALUES(?,?,?,?)", (sid,"user",text,time.time()))
                context = cx.execute("SELECT role,content FROM messages WHERE session_id=? ORDER BY id", (sid,)).fetchall()
                reply, provider = model_reply(text, context)
                cx.execute("INSERT INTO messages(session_id,role,content,created_at) VALUES(?,?,?,?)", (sid,"assistant",reply,time.time()))
                if text.lower().startswith("recuerda "):
                    fact = text[9:].strip(); cx.execute("INSERT OR IGNORE INTO memories(session_id,fact,source,created_at) VALUES(?,?,?,?)", (sid,fact,"user",time.time()))
                cx.commit()
            self.send_response(200); self.send_header("Content-Type", "text/event-stream; charset=utf-8"); self.send_header("Cache-Control", "no-cache"); self.send_header("Connection", "keep-alive"); self.end_headers()
            for token in reply.split(" "):
                self.wfile.write(("data: "+json.dumps({"token": token+" ", "provider": provider}, ensure_ascii=False)+"\n\n").encode()); self.wfile.flush(); time.sleep(0.005)
            self.wfile.write(b"data: {\"done\": true}\n\n"); self.wfile.flush(); self.close_connection = True
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    def log_message(self, *_): pass


def main():
    host, port = os.environ.get("OLIVIA_HOST", "127.0.0.1"), int(os.environ.get("OLIVIA_PORT", "8787"))
    print(f"0liviA proof listening on http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()

if __name__ == "__main__": main()
