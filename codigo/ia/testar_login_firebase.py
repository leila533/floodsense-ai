import argparse
import re
import sys
from pathlib import Path

import requests


# ============================================================
# FLOODSENSE AI - TESTE DO LOGIN DO DISPOSITIVO NO FIREBASE
#
# O firmware do ESP32 faz um login (e-mail + senha + chave de API) para
# poder gravar no Firebase. Quando isso falha ele só mostra "HTTP 400".
# Este script lê do(s) arquivo(s) do firmware exatamente os mesmos
# valores que o ESP32 usa, faz o MESMO login pelo computador e mostra a
# mensagem de erro que o Google devolve.
#
# NÃO imprime senha nem chave. NÃO escreve no Firebase (só pede um token).
#
# Uso (a partir de codigo\\ia):
#   python testar_login_firebase.py
#   python testar_login_firebase.py ..\\..\\firmware\\FloodSense_FS001_v3\\secrets.h
# Sem argumentos, procura *.ino e secrets.h dentro da pasta firmware do projeto.
# ============================================================

PASTA_PROJETO = Path(__file__).resolve().parent.parent.parent
LOGIN_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
CAMPOS = ("FIREBASE_API_KEY", "DEVICE_EMAIL", "DEVICE_PASSWORD")

EXPLICACAO = {
    "INVALID_LOGIN_CREDENTIALS": "e-mail ou senha do firmware não conferem com o usuário do Firebase "
                                 "(ou o usuário não existe).",
    "INVALID_PASSWORD": "a senha do firmware não confere com a do usuário no Firebase.",
    "EMAIL_NOT_FOUND": "não existe usuário com esse e-mail no Authentication.",
    "USER_DISABLED": "o usuário está desativado no Authentication.",
    "OPERATION_NOT_ALLOWED": "o login por E-mail/senha está desativado "
                             "(Authentication > Método de login).",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "muitas tentativas seguidas: o Google bloqueou por um tempo. "
                                   "Desligue o ESP32 por 15-30 min e teste de novo.",
    "API key not valid. Please pass a valid API key.": "a chave de API do firmware está errada.",
    "API_KEY_INVALID": "a chave de API do firmware está errada.",
    "MISSING_PASSWORD": "a senha está vazia no firmware.",
    "INVALID_EMAIL": "o e-mail do firmware tem formato inválido.",
}


def _desescapar(texto):
    return (texto.replace('\\"', '"').replace("\\\\", "\\"))


def extrair_config(texto):
    """Lê FIREBASE_API_KEY, DEVICE_EMAIL e DEVICE_PASSWORD de um .ino/.h.
    Aceita `const char* NOME = "valor";` e `#define NOME "valor"`."""
    config = {}
    for nome in CAMPOS:
        achou = re.search(rf'\b{nome}\b\s*=?\s*"((?:[^"\\]|\\.)*)"', texto)
        if achou:
            config[nome] = _desescapar(achou.group(1))
    return config


def mascarar_email(email):
    usuario, _, dominio = email.partition("@")
    return f"{usuario[:4]}***@{dominio}" if dominio else "***"


def testar_login(config, post=requests.post):
    """Devolve (ok, mensagem). Não imprime nada."""
    try:
        resposta = post(f"{LOGIN_URL}?key={config['FIREBASE_API_KEY']}",
                        json={"email": config["DEVICE_EMAIL"],
                              "password": config["DEVICE_PASSWORD"],
                              "returnSecureToken": True},
                        timeout=20)
    except requests.exceptions.RequestException as erro:
        return False, f"sem conexão com o Google ({type(erro).__name__})"

    if resposta.status_code == 200:
        return True, "LOGIN OK"

    try:
        mensagem = resposta.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        mensagem = f"HTTP {resposta.status_code} sem mensagem"
    return False, mensagem


def descobrir_arquivos():
    pasta = PASTA_PROJETO / "firmware"
    if not pasta.exists():
        return []
    return sorted(set(pasta.rglob("*.ino")) | set(pasta.rglob("secrets.h")))


def main(argv=None, post=requests.post):
    parser = argparse.ArgumentParser(description="FloodSense AI - testa o login do dispositivo no Firebase")
    parser.add_argument("arquivos", nargs="*", type=Path,
                        help="arquivos do firmware (.ino / secrets.h). Padrão: pasta firmware do projeto")
    args = parser.parse_args(argv)

    arquivos = args.arquivos or descobrir_arquivos()
    if not arquivos:
        print("Nenhum arquivo de firmware encontrado. Passe o caminho do .ino ou do secrets.h.")
        return 1

    print("=" * 70)
    print("FLOODSENSE AI - TESTE DO LOGIN DO DISPOSITIVO (não imprime senha nem chave)")
    print("=" * 70)

    # junta os valores por arquivo; um .ino pode depender do secrets.h da mesma pasta
    testados, sem_config, falhas = 0, [], 0
    for arquivo in arquivos:
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError as erro:
            print(f"\n{arquivo}: não foi possível ler ({erro})")
            falhas += 1
            continue

        config = extrair_config(texto)
        if len(config) < len(CAMPOS):
            sem_config.append((arquivo, [c for c in CAMPOS if c not in config]))
            continue

        testados += 1
        ok, mensagem = testar_login(config, post)
        print(f"\nArquivo: {arquivo}")
        print(f"  e-mail testado: {mascarar_email(config['DEVICE_EMAIL'])}")
        print(f"  resultado: {mensagem}")
        if not ok:
            falhas += 1
            if mensagem in EXPLICACAO:
                print(f"  significado: {EXPLICACAO[mensagem]}")

    for arquivo, faltando in sem_config:
        print(f"\n{arquivo}: não tem todos os campos no próprio arquivo (faltam: {', '.join(faltando)}).")

    if testados == 0:
        print("\nNenhum arquivo trouxe os três valores (chave, e-mail e senha). "
              "Se estão em secrets.h, passe esse arquivo como argumento.")
        return 1

    print()
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
