#!/usr/bin/env python3
"""
WHOOP OAuth 2.0 — obter access_token e refresh_token iniciais.

Uso:
  WHOOP_CLIENT_ID=xxx WHOOP_CLIENT_SECRET=yyy python scripts/whoop_auth.py

Configure os tokens impressos como GitHub Secrets:
  WHOOP_CLIENT_ID, WHOOP_CLIENT_SECRET, WHOOP_ACCESS_TOKEN, WHOOP_REFRESH_TOKEN
"""

import http.server
import os
import sys
import urllib.parse
import urllib.request
import json
import webbrowser
from threading import Event

CLIENT_ID = os.environ.get("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.environ.get("WHOOP_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080"
SCOPES = "offline read:recovery read:cycles read:sleep read:workout read:profile read:body_measurement"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

if not CLIENT_ID or not CLIENT_SECRET:
    sys.exit("Erro: defina WHOOP_CLIENT_ID e WHOOP_CLIENT_SECRET como variáveis de ambiente.")

auth_code = None
stop_event = Event()


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Autorizado. Pode fechar esta aba.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>Erro: code nao encontrado.</h2>")
        stop_event.set()

    def log_message(self, *args):
        pass


def build_auth_url():
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "response_type": "code",
    })
    return f"{AUTH_URL}?{params}"


def exchange_code(code):
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


url = build_auth_url()
print(f"\nAbrindo URL de autorização:\n{url}\n")
webbrowser.open(url)

server = http.server.HTTPServer(("localhost", 8080), CallbackHandler)
print("Aguardando callback em http://localhost:8080 ...")
stop_event.wait(timeout=0)
while not stop_event.is_set():
    server.handle_request()
server.server_close()

if not auth_code:
    sys.exit("Erro: nenhum code recebido.")

print("\nTrocando code por tokens...")
tokens = exchange_code(auth_code)

print("\n--- Configure estes valores como GitHub Secrets ---")
print(f"WHOOP_CLIENT_ID     = {CLIENT_ID}")
print(f"WHOOP_CLIENT_SECRET = {CLIENT_SECRET}")
print(f"WHOOP_ACCESS_TOKEN  = {tokens.get('access_token')}")
print(f"WHOOP_REFRESH_TOKEN = {tokens.get('refresh_token')}")
print("---------------------------------------------------\n")
