import sys
from datetime import datetime
from pathlib import Path

import requests

# ============================================================
# FLOODSENSE AI - TESTE DO TELEGRAM (manda UMA mensagem e sai)
#
# Lê TELEGRAM_TOKEN e TELEGRAM_CHAT_ID do segredos.env (codigo\ia ou codigo),
# envia uma mensagem de teste e diz se o Telegram aceitou.
# NÃO imprime o token.
# Uso (em codigo\ia):  python testar_telegram.py
# ============================================================

PASTA = Path(__file__).resolve().parent
CANDIDATOS = [PASTA / "segredos.env", PASTA.parent / "segredos.env"]


def ler_env():
    valores = {}
    for caminho in CANDIDATOS:
        if not caminho.exists():
            continue
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            nome, valor = linha.split("=", 1)
            valores.setdefault(nome.strip(), valor.strip().strip('"').strip("'"))
    return valores


def main():
    env = ler_env()
    token, chat = env.get("TELEGRAM_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Faltam TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID no segredos.env.")
        return 1
    texto = f"Teste FloodSense AI - {datetime.now():%d/%m/%Y %H:%M}. Se você leu isto, o alerta no Telegram funciona."
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": texto}, timeout=20)
    except requests.exceptions.RequestException as erro:
        print(f"Sem conexão com o Telegram ({type(erro).__name__}).")
        return 1
    if r.status_code == 200:
        print("Mensagem enviada. Confira no Telegram.")
        return 0
    try:
        motivo = r.json().get("description", "sem descrição")
    except ValueError:
        motivo = "sem descrição"
    print(f"O Telegram recusou (HTTP {r.status_code}): {motivo}")
    return 1


if __name__ == "__main__":
    sys.exit(main())