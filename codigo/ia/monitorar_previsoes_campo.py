import argparse
import csv
import math
import time
from datetime import datetime
from pathlib import Path

import requests


# ============================================================
# FLOODSENSE AI - MONITOR DE PREVISÕES EM CAMPO (SOMENTE LEITURA)
#
# Por quê: o serviço grava cada previsão no MESMO nó do Firebase
# (/ai_predictions/FS-001) e a anterior é sobrescrita. Sem um registro,
# não há como saber depois se a previsão de +60 min acertou.
#
# O que faz: a cada INTERVALO segundos lê (GET) esse nó e acrescenta
# uma linha em codigo/previsoes_campo_log.csv sempre que aparece uma
# leitura nova (chave: reading_timestamp). Depois, o script
# avaliar_previsoes_campo.py compara cada previsão com o nível real
# medido 60 min depois.
#
# Só faz GET. NÃO escreve no Firebase, não altera o serviço, o modelo,
# o firmware nem o dashboard.
#
# Uso (deixe rodando em paralelo ao serviço de previsão):
#   cd codigo\ia
#   python monitorar_previsoes_campo.py
# Encerra com Ctrl+C. Opções: --once, --intervalo SEGUNDOS, --log ARQUIVO
# ============================================================

PASTA_CODIGO = Path(__file__).resolve().parent.parent

FIREBASE_HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
SENSOR_ID = "FS-001"
PREDICTION_URL = f"{FIREBASE_HOST}/ai_predictions/{SENSOR_ID}.json"

LOG_PATH = PASTA_CODIGO / "previsoes_campo_log.csv"
INTERVALO_PADRAO_SEGUNDOS = 60

COLUNAS = [
    "logged_at", "reading_timestamp", "generated_at",
    "current_level_cm", "predicted_level_60min_cm", "status",
    "prediction_mode", "available_lags", "model_algorithm", "model_version",
    "selection_metric", "selection_mae_test_cm", "initial_fallback",
]


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def ler_previsao(url=PREDICTION_URL):
    """GET do nó de previsão. Erros HTTP propagam (não viram 'vazio')."""
    resposta = requests.get(url, timeout=20)
    resposta.raise_for_status()
    dados = resposta.json()

    if dados is None:
        return None
    if not isinstance(dados, dict):
        raise ValueError(f"Formato inesperado em {url}: {type(dados).__name__}")
    return dados


def validar(p):
    """Devolve (ok, motivo). Só registra previsões coerentes."""
    try:
        int(p.get("reading_timestamp"))
    except (TypeError, ValueError):
        return False, "reading_timestamp ausente ou inválido"
    if _num(p.get("current_level_cm")) is None:
        return False, "current_level_cm ausente ou não numérico"
    if _num(p.get("predicted_level_60min_cm")) is None:
        return False, "predicted_level_60min_cm ausente ou não numérico"
    if p.get("sensor_id", SENSOR_ID) != SENSOR_ID:
        return False, f"sensor_id={p.get('sensor_id')} (esperado {SENSOR_ID})"
    if p.get("horizon_minutes", 60) != 60:
        return False, f"horizon_minutes={p.get('horizon_minutes')} (esperado 60)"
    return True, ""


def _lags_texto(valor):
    # No STARTUP o Firebase costuma descartar o array vazio: o campo some.
    if valor is None:
        return ""
    if isinstance(valor, dict):
        valor = list(valor.values())
    if isinstance(valor, (list, tuple)):
        return ";".join(str(v) for v in valor)
    return str(valor)


def _chaves_existentes(caminho):
    if not caminho.exists():
        return set()
    with open(caminho, newline="", encoding="utf-8") as f:
        return {linha["reading_timestamp"] for linha in csv.DictReader(f)}


def registrar(p, caminho=LOG_PATH):
    """Acrescenta a previsão ao CSV. Retorna 'novo', 'duplicado' ou 'invalido: ...'."""
    ok, motivo = validar(p)
    if not ok:
        return f"invalido: {motivo}"

    chave = str(int(p["reading_timestamp"]))
    if chave in _chaves_existentes(caminho):
        return "duplicado"

    novo_arquivo = not caminho.exists()
    linha = {
        "logged_at": datetime.now().isoformat(timespec="seconds"),
        "reading_timestamp": chave,
        "generated_at": p.get("generated_at", ""),
        "current_level_cm": p.get("current_level_cm"),
        "predicted_level_60min_cm": p.get("predicted_level_60min_cm"),
        "status": p.get("status", ""),
        "prediction_mode": p.get("prediction_mode", ""),
        "available_lags": _lags_texto(p.get("available_lags")),
        "model_algorithm": p.get("model_algorithm", ""),
        "model_version": p.get("model_version", ""),
        "selection_metric": p.get("selection_metric", ""),
        "selection_mae_test_cm": p.get("selection_mae_test_cm", ""),
        "initial_fallback": p.get("initial_fallback", ""),
    }
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo_arquivo:
            escritor.writeheader()
        escritor.writerow(linha)
    return "novo"


def ciclo(caminho=LOG_PATH):
    """Um ciclo. Nunca levanta exceção (exceto Ctrl+C)."""
    try:
        p = ler_previsao()
        if p is None:
            log("Nenhuma previsão publicada ainda em /ai_predictions/FS-001.")
            return None
        resultado = registrar(p, caminho)
        if resultado == "novo":
            log(f"Registrada: leitura {p.get('reading_timestamp')} | "
                f"atual={p.get('current_level_cm')} cm | "
                f"+60min={p.get('predicted_level_60min_cm')} cm | "
                f"modo={p.get('prediction_mode')}")
        elif resultado.startswith("invalido"):
            log(f"[AVISO] previsão ignorada ({resultado}).")
        return resultado
    except requests.exceptions.RequestException as erro:
        log(f"[ERRO] Firebase indisponível: {erro}")
    except Exception as erro:  # noqa: BLE001
        log(f"[ERRO] ciclo falhou ({type(erro).__name__}): {erro}")
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="FloodSense AI - monitor de previsões em campo (somente leitura)")
    parser.add_argument("--once", action="store_true", help="um único ciclo")
    parser.add_argument("--intervalo", type=int, default=INTERVALO_PADRAO_SEGUNDOS,
                        help="segundos entre leituras (padrão: %(default)s)")
    parser.add_argument("--log", type=Path, default=LOG_PATH,
                        help="CSV de saída (padrão: %(default)s)")
    args = parser.parse_args(argv)
    if args.intervalo < 1:
        parser.error("--intervalo deve ser de pelo menos 1 segundo")

    print("=" * 60)
    print("FLOODSENSE AI - MONITOR DE PREVISÕES EM CAMPO (somente leitura)")
    print(f"Registro: {args.log}")
    print("=" * 60)

    try:
        if args.once:
            return 0 if ciclo(args.log) is not None else 1
        while True:
            ciclo(args.log)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print()
        log("Monitor encerrado pelo usuário (Ctrl+C).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())