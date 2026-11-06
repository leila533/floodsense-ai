import sys
from pathlib import Path

import requests

# ============================================================
# FLOODSENSE AI - DESCOBRE O TELEGRAM_CHAT_ID
#
# Lê TELEGRAM_TOKEN do segredos.env (na pasta codigo ou codigo\ia),
# pergunta ao Telegram quais conversas falaram com o bot e imprime
# só o ID, o tipo e o nome de cada uma. NÃO imprime o token.
#
# Antes: mande "oi" para o bot (ou escreva no grupo/canal onde ele está).
# Uso (em codigo\ia):  python descobrir_chat_id_telegram.py
# ============================================================

PASTA = Path(__file__).resolve().parent
CANDIDATOS = [PASTA / "segredos.env", PASTA.parent / "segredos.env"]


def ler_token():
    for caminho in CANDIDATOS:
        if not caminho.exists():
            continue
        for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
            linha = linha.strip()
            for nome in ("TELEGRAM_TOKEN", "TELEGRAM_BOT_TOKEN"):
                if linha.startswith(nome + "="):
                    return linha.split("=", 1)[1].strip().strip('"').strip("'"), caminho
    return None, None


def extrair_chats(resposta_json):
    chats = {}
    for item in resposta_json.get("result", []):
        for chave in ("message", "edited_message", "channel_post", "my_chat_member"):
            msg = item.get(chave)
            if msg and "chat" in msg:
                chat = msg["chat"]
                nome = chat.get("title") or " ".join(
                    p for p in (chat.get("first_name"), chat.get("last_name")) if p) or "(sem nome)"
                chats[chat["id"]] = (chat.get("type", "?"), nome)
    return chats


def main():
    token, caminho = ler_token()
    if not token or "COLE_AQUI" in token:
        print("Não achei TELEGRAM_TOKEN preenchido no segredos.env "
              f"(procurei em: {', '.join(str(c) for c in CANDIDATOS)}).")
        return 1
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20)
    except requests.exceptions.RequestException as erro:
        print(f"Sem conexão com o Telegram ({type(erro).__name__}).")
        return 1
    if r.status_code in (401, 404):
        print("O Telegram recusou o token (revogado ou digitado errado). "
              "Pegue o token novo no BotFather e confira o TELEGRAM_TOKEN.")
        return 1
    if r.status_code != 200:
        print(f"O Telegram respondeu HTTP {r.status_code}.")
        return 1

    chats = extrair_chats(r.json())
    if not chats:
        print("Nenhuma conversa encontrada. Mande 'oi' para o bot (ou escreva no grupo/canal "
              "onde ele está) e rode de novo.")
        return 1
    print(f"Token lido de: {caminho.name} (não é mostrado).\n")
    print("Conversas que falaram com o bot:")
    for cid, (tipo, nome) in chats.items():
        print(f"   TELEGRAM_CHAT_ID={cid}    ({tipo}: {nome})")
    print("\nCopie a linha da conversa que vai receber os alertas para o segredos.env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())