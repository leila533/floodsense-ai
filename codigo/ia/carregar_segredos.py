"""
Carrega as credenciais do arquivo segredos.env (fora do Git) para as
variáveis de ambiente do Python.

Uso: chame carregar() no início do script. Valores já definidos no
PowerShell têm prioridade sobre o arquivo.
"""

import os
from pathlib import Path

ARQUIVO = Path(__file__).with_name("segredos.env")


def carregar():
    if not ARQUIVO.exists():
        print(f"[AVISO] Arquivo {ARQUIVO.name} não encontrado. Crie-o a partir de segredos_exemplo.env.")
        return

    for linha in ARQUIVO.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valor = valor.strip().strip('"').strip("'")
        os.environ.setdefault(chave.strip(), valor)