"""
FLOODSENSE AI - PUBLICADOR DA PREVISÃO (v1)

Roda previsao_floodsense_v3.py a cada 5 minutos e grava o resultado em
/ai_predictions/FS-001 no Firebase, que é o nó lido pelo dashboard.

Coloque este arquivo na mesma pasta de previsao_floodsense_v3.py (codigo\\ia).

Antes de rodar, defina no terminal (PowerShell), na mesma janela:

    $env:FS_API_KEY = "sua_apiKey_do_index_html"
    $env:FS_DEVICE_EMAIL = "dispositivo-fs001@floodsense.ai"
    $env:FS_DEVICE_PASSWORD = "senha_do_dispositivo"

Depois rode:  python publicar_previsao_firebase.py
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from carregar_segredos import carregar as _carregar_segredos
_carregar_segredos()

# Permite importar previsao_floodsense_v3 mesmo rodando de outra pasta
sys.path.insert(0, str(Path(__file__).resolve().parent))
import previsao_floodsense_v3 as prev  # noqa: E402


INTERVALO_S = 300               # 5 minutos
IDADE_MAX_LEITURA_MIN = 15      # não publica se o último dado do histórico for mais antigo
LIMITE_ATENCAO = 60             # cm (mesmo critério do dashboard)
LIMITE_CRITICO = 90             # cm


def login_dispositivo():
    api_key = os.environ.get("FS_API_KEY")
    email = os.environ.get("FS_DEVICE_EMAIL")
    senha = os.environ.get("FS_DEVICE_PASSWORD")

    if not (api_key and email and senha):
        raise RuntimeError(
            "Defina FS_API_KEY, FS_DEVICE_EMAIL e FS_DEVICE_PASSWORD "
            "antes de rodar."
        )

    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        f"accounts:signInWithPassword?key={api_key}"
    )
    r = requests.post(
        url,
        json={"email": email, "password": senha, "returnSecureToken": True},
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Falha no login do dispositivo: HTTP {r.status_code} {r.text[:200]}")

    return r.json()["idToken"]


def status_da_previsao(valor):
    if valor >= LIMITE_CRITICO:
        return "critical"
    if valor >= LIMITE_ATENCAO:
        return "warning"
    return "normal"


def publicar_uma_vez(token):
    pacote = prev.carregar_modelo()
    modelo = pacote["modelo"]
    features = pacote["features"]

    df, path_usado = prev.buscar_historico_operacional()

    # Idade da última leitura do histórico
    ultimo_ts_s = int(df["timestamp"].iloc[-1])
    if ultimo_ts_s > 1e12:
        ultimo_ts_s = ultimo_ts_s / 1000
    idade_min = (time.time() - ultimo_ts_s) / 60

    if idade_min > IDADE_MAX_LEITURA_MIN:
        print(
            f"[AVISO] Última leitura do histórico tem {idade_min:.0f} min. "
            f"Não publicado (limite {IDADE_MAX_LEITURA_MIN} min)."
        )
        return

    X, dados_atual, _ = prev.construir_features_v3(df, features)
    previsao = float(modelo.predict(X)[0])
    atual = float(dados_atual["water_level"])

    agora = datetime.now(timezone.utc)

    corpo = {
        "sensor_id": prev.SENSOR_ID,
        "current_level_cm": round(atual, 2),
        "predicted_level_60min_cm": round(previsao, 2),
        "horizon_minutes": 60,
        "status": status_da_previsao(previsao),
        "generated_at": agora.isoformat(timespec="milliseconds"),
        "model": pacote.get("nome", type(modelo).__name__),
        "model_algorithm": type(modelo).__name__,
        "model_version": str(pacote.get("feature_version", "desconhecida")),
        "prediction_mode": str(pacote.get("feature_set", "desconhecido")),
        "available_lags": ["5", "15", "30"],
        "sensor_unit": "cm",
        "real_sensor_compatible": True,
        "historico_usado": path_usado,
    }

    url = f"{prev.FIREBASE_HOST}/ai_predictions/{prev.SENSOR_ID}.json?auth={token}"
    r = requests.put(url, json=corpo, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Falha ao gravar previsão: HTTP {r.status_code} {r.text[:200]}")

    print(
        f"[OK {agora.astimezone().strftime('%H:%M:%S')}] "
        f"atual={atual:.2f} cm · previsão +60 min={previsao:.2f} cm · "
        f"status={corpo['status']} · publicado em /ai_predictions"
    )


def main():
    print("=" * 70)
    print("FLOODSENSE AI - PUBLICADOR DA PREVISÃO")
    print("Ctrl+C para parar")
    print("=" * 70)

    while True:
        try:
            token = login_dispositivo()
            publicar_uma_vez(token)
        except KeyboardInterrupt:
            print("Parado pelo usuário.")
            break
        except Exception as erro:
            print(f"[ERRO] {erro}")

        time.sleep(INTERVALO_S)


if __name__ == "__main__":
    main()