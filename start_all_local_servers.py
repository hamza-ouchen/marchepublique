"""Start every SOU9NA local server without Docker.

Loads the same env files as start_local_servers.py, starts only services whose
port is free, and leaves already-running servers untouched. Logs go to
server-logs/; no credentials are printed.
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
LOGS = ROOT / 'server-logs'
LOGS.mkdir(exist_ok=True)

for env_file in (ROOT / '02-backend' / '.env',
                 ROOT / '04-langgraph' / 'regisseur' / '.env'):
    if env_file.exists():
        load_dotenv(env_file, override=False)

P315 = r'C:\Users\PC\AppData\Local\Programs\Python\Python315\python.exe'
P313 = r'C:\Users\PC\AppData\Local\Programs\Python\Python313\python.exe'
NODE = r'C:\Program Files\nodejs\node.exe'

paths = [
    ROOT, ROOT / '02-backend', ROOT / '04-langgraph',
    ROOT / '04-langgraph' / 'agents', ROOT / '04-langgraph' / 'inspecteur',
    ROOT / '04-langgraph' / 'regisseur', ROOT / '03-agentic-ai' / 'compagnon',
    ROOT / '05-mcp-server' / 'base-donnees', ROOT / '05-mcp-server' / 'canaux',
    ROOT / '05-mcp-server' / 'base-connaissances',
    ROOT / '05-mcp-server' / 'portail-marches',
    ROOT / 'db-backups' / 'oracle-runtime-20261127_174233' / 'deps',
]
os.environ['PYTHONPATH'] = os.pathsep.join(str(p) for p in paths)
for key, value in {
    'MODE_AGENTS': 'reel',
    'SOU9NA_AGENTIC_FLOW': '0',
    'SOU9NA_AGENTIC_FIRST': '0',
    'MCP_TRANSPORT': 'streamable-http',
    'FASTMCP_HOST': '127.0.0.1',
    'MCP_API_KEY': (os.getenv('MCP_AUTH_TOKEN')
                    or os.getenv('MCP_API_KEY') or 'sou9na-mcp-2026'),
    'REGISSEUR_URL': 'http://127.0.0.1:8100',
    'INSPECTEUR_URL': 'http://127.0.0.1:8101',
    'COMPAGNON_URL': 'http://127.0.0.1:8102',
    'JUGE_URL': 'http://127.0.0.1:8103',
    'CONCIERGE_URL': 'http://127.0.0.1:8104',
    'SOU9NA_API_URL': 'http://127.0.0.1:8000',
}.items():
    os.environ.setdefault(key, value)
os.environ.setdefault('MCP_AUTH_TOKEN', os.getenv('MCP_API_KEY') or 'sou9na-mcp-2026')
os.environ.setdefault('CANAUX_MCP_API_KEY', os.environ['MCP_API_KEY'])

SERVICES = [
    {'name': 'api', 'port': 8000, 'cwd': ROOT / '02-backend', 'py': P315,
     'command': [P315, '-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000']},
    {'name': 'frontend', 'port': 3000, 'cwd': ROOT / 'frontend', 'py': NODE,
     'command': [NODE, str(ROOT / 'frontend' / 'node_modules' / 'next' / 'dist' / 'bin' / 'next'),
                 'start', '-p', '3000']},
    {'name': 'regisseur', 'port': 8100, 'cwd': ROOT / '04-langgraph' / 'regisseur', 'py': P313,
     'command': [P313, '-m', 'uvicorn', 'serveur_http:_app', '--host', '127.0.0.1', '--port', '8100']},
    {'name': 'inspecteur', 'port': 8101, 'cwd': ROOT / '04-langgraph' / 'agents', 'py': P313,
     'command': [P313, '-m', 'uvicorn', 'serveur_inspecteur:app', '--host', '127.0.0.1', '--port', '8101']},
    {'name': 'compagnon', 'port': 8102, 'cwd': ROOT / '04-langgraph' / 'agents', 'py': P313,
     'command': [P313, '-m', 'uvicorn', 'serveur_compagnon:app', '--host', '127.0.0.1', '--port', '8102']},
    {'name': 'juge', 'port': 8103, 'cwd': ROOT / '04-langgraph' / 'agents', 'py': P313,
     'command': [P313, '-m', 'uvicorn', 'serveur_juge:app', '--host', '127.0.0.1', '--port', '8103']},
    {'name': 'concierge', 'port': 8104, 'cwd': ROOT / '04-langgraph' / 'agents', 'py': P315,
     'command': [P315, '-m', 'uvicorn', 'serveur_concierge:app', '--host', '127.0.0.1', '--port', '8104']},
    {'name': 'mcp-base-donnees', 'port': 8201, 'cwd': ROOT / '05-mcp-server' / 'base-donnees', 'py': P313,
     'command': [P313, 'serveur.py'], 'env': {'FASTMCP_PORT': '8201'}},
    {'name': 'mcp-portail-marches', 'port': 8202, 'cwd': ROOT / '05-mcp-server' / 'portail-marches', 'py': P315,
     'command': [P315, 'serveur.py'], 'env': {'FASTMCP_PORT': '8202'}},
    {'name': 'mcp-base-connaissances', 'port': 8203, 'cwd': ROOT / '05-mcp-server' / 'base-connaissances', 'py': P315,
     'command': [P315, 'serveur.py'], 'env': {'FASTMCP_PORT': '8203'}},
    {'name': 'mcp-canaux', 'port': 8204, 'cwd': ROOT / '05-mcp-server' / 'canaux', 'py': P313,
     'command': [P313, 'serveur.py'], 'env': {'FASTMCP_PORT': '8204'}},
]


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(('127.0.0.1', port)) != 0


def main() -> None:
    started = {}
    for service in SERVICES:
        name, port = service['name'], service['port']
        if not port_free(port):
            print(f'SKIP  {name:<24} port {port} already listening')
            continue
        if not Path(service['py']).exists():
            print(f'MISS  {name:<24} executable not found')
            continue
        env = os.environ.copy()
        env.update(service.get('env', {}))
        log_out = (LOGS / f'{name}.stdout.log').open('w', encoding='utf-8')
        log_err = (LOGS / f'{name}.stderr.log').open('w', encoding='utf-8')
        proc = subprocess.Popen(
            service['command'], cwd=service['cwd'], env=env,
            stdin=subprocess.DEVNULL, stdout=log_out, stderr=log_err,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        started[name] = {'pid': proc.pid, 'port': port}
        print(f'START {name:<24} port {port} pid {proc.pid}')
    (LOGS / 'started-all.json').write_text(
        json.dumps(started, ensure_ascii=False, indent=2), encoding='utf-8'
    )


if __name__ == '__main__':
    main()
