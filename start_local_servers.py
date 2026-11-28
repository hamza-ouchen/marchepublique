"""Start any missing local SOU9NA servers without Docker.

Loads the same env files as docker-compose.yml, sets the same defaults, and
launches only services whose port is free. Existing servers are left untouched.
Logs go to server-logs/; no credentials are printed.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "server-logs"
LOGS.mkdir(exist_ok=True)

# Same env files as docker-compose.yml (values never printed).
for env_file in (ROOT / "02-backend" / ".env",
                 ROOT / "04-langgraph" / "regisseur" / ".env"):
    if env_file.exists():
        load_dotenv(env_file, override=False)

paths = [
    ROOT, ROOT / "02-backend", ROOT / "04-langgraph",
    ROOT / "04-langgraph" / "agents", ROOT / "04-langgraph" / "inspecteur",
    ROOT / "04-langgraph" / "regisseur", ROOT / "03-agentic-ai" / "compagnon",
    ROOT / "05-mcp-server" / "base-donnees", ROOT / "05-mcp-server" / "canaux",
    ROOT / "05-mcp-server" / "base-connaissances",
    ROOT / "05-mcp-server" / "portail-marches",
]
os.environ["PYTHONPATH"] = os.pathsep.join(str(p) for p in paths)
for key, value in {
    "MODE_AGENTS": "reel",
    "SOU9NA_AGENTIC_FLOW": "0",
    "SOU9NA_AGENTIC_FIRST": "0",
    "MCP_TRANSPORT": "streamable-http",
    "FASTMCP_HOST": "127.0.0.1",
    "MCP_API_KEY": (os.getenv("MCP_AUTH_TOKEN")
                    or os.getenv("MCP_API_KEY") or "sou9na-mcp-2026"),
    "REGISSEUR_URL": "http://127.0.0.1:8100",
    "INSPECTEUR_URL": "http://127.0.0.1:8101",
    "COMPAGNON_URL": "http://127.0.0.1:8102",
    "JUGE_URL": "http://127.0.0.1:8103",
    "CONCIERGE_URL": "http://127.0.0.1:8104",
    "SOU9NA_API_URL": "http://127.0.0.1:8000",
}.items():
    os.environ.setdefault(key, value)
os.environ.setdefault(
    "MCP_API_KEY", os.getenv("MCP_AUTH_TOKEN") or "sou9na-mcp-2026"
)
os.environ.setdefault("MCP_AUTH_TOKEN", os.getenv("MCP_API_KEY") or "sou9na-mcp-2026")
os.environ.setdefault("CANAUX_MCP_API_KEY", os.environ["MCP_API_KEY"])

SERVICES = [
    {
        "name": "api",
        "port": 8000,
        "cwd": ROOT / "02-backend",
        "command": [sys.executable, "-m", "uvicorn", "api:app",
                    "--host", "127.0.0.1", "--port", "8000"],
        "env": {},
    },
    {
        "name": "concierge",
        "port": 8104,
        "cwd": ROOT / "04-langgraph" / "agents",
        "command": [sys.executable, "-m", "uvicorn", "serveur_concierge:app",
                    "--host", "127.0.0.1", "--port", "8104"],
        "env": {"CONCIERGE_PORT": "8104"},
    },
    {
        "name": "mcp-portail-marches",
        "port": 8202,
        "cwd": ROOT / "05-mcp-server" / "portail-marches",
        "command": [sys.executable, "serveur.py"],
        "env": {"FASTMCP_PORT": "8202"},
    },
    {
        "name": "mcp-base-connaissances",
        "port": 8203,
        "cwd": ROOT / "05-mcp-server" / "base-connaissances",
        "command": [sys.executable, "serveur.py"],
        "env": {"FASTMCP_PORT": "8203"},
    },
]


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def main() -> None:
    started = {}
    for service in SERVICES:
        port = service["port"]
        if not port_free(port):
            print(f"SKIP  {service['name']:<24} port {port} already listening")
            continue
        env = os.environ.copy()
        env.update(service["env"])
        log_out = (LOGS / f"{service['name']}.stdout.log").open("w", encoding="utf-8")
        log_err = (LOGS / f"{service['name']}.stderr.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(
            service["command"], cwd=service["cwd"], env=env,
            stdin=subprocess.DEVNULL, stdout=log_out, stderr=log_err,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        started[service["name"]] = {"pid": proc.pid, "port": port}
        print(f"START {service['name']:<24} port {port} pid {proc.pid}")
    (LOGS / "started.json").write_text(
        json.dumps(started, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
