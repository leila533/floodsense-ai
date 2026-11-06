from pathlib import Path

import requests
import numpy as np
import pandas as pd
import joblib


# ============================================================
# FLOODSENSE AI - PREVISÃO V3
# ============================================================
#
# Este arquivo deve usar EXATAMENTE as mesmas features do
# treinar_modelo_real_esp32.py V3.
#
# O modelo carrega do próprio .pkl a lista de features escolhida.
# Assim, não existe risco de o dashboard mandar colunas diferentes
# das usadas no treinamento.
#
# CORREÇÃO (v3.1): o script passa a ler SOMENTE
# /sensor_history_treinamento, que é onde o firmware grava
# (a cada 60 s). Antes ele tentava /sensor_history primeiro e,
# se esse nó tivesse dados antigos, usava-o por engano.
# ============================================================


PASTA_CODIGO = Path(__file__).resolve().parent.parent

FIREBASE_HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
SENSOR_ID = "FS-001"

MODEL_PATH = PASTA_CODIGO / "floodsense_model_60min_esp32.pkl"

# Histórico gravado pelo firmware do ESP32 (a cada 60 s).
HISTORY_PATHS = [
    f"/sensor_history_treinamento/{SENSOR_ID}.json",
]

TOLERANCIA_LAG_MIN = 2


def carregar_modelo():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Modelo não encontrado: {MODEL_PATH}"
        )

    pacote = joblib.load(MODEL_PATH)

    if not isinstance(pacote, dict):
        raise RuntimeError(
            "O arquivo do modelo não contém o pacote esperado."
        )

    if "modelo" not in pacote or "features" not in pacote:
        raise RuntimeError(
            "Modelo incompatível: faltam 'modelo' ou 'features'."
        )

    return pacote


def buscar_historico(path):
    url = f"{FIREBASE_HOST}{path}"

    resposta = requests.get(url, timeout=20)

    if resposta.status_code != 200:
        return pd.DataFrame(columns=["timestamp", "water_level"])

    dados = resposta.json() or {}

    registros = []

    for timestamp, valor in dados.items():
        if not isinstance(valor, dict):
            continue

        nivel = valor.get("level")
        if nivel is None:
            continue

        try:
            registros.append({
                "timestamp": int(timestamp),
                "water_level": float(nivel),
            })
        except (ValueError, TypeError):
            continue

    if not registros:
        return pd.DataFrame(columns=["timestamp", "water_level"])

    return (
        pd.DataFrame(registros)
        .drop_duplicates("timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def buscar_historico_operacional():
    """
    Lê o histórico gravado pelo firmware.
    Falha com mensagem clara se estiver vazio.
    """
    for path in HISTORY_PATHS:
        df = buscar_historico(path)

        if not df.empty:
            return df, path

    raise RuntimeError(
        "Nenhuma leitura encontrada no Firebase. "
        "Verifique se o ESP32 está gravando o histórico."
    )


def buscar_leitura_proxima(
    timestamps,
    timestamp_alvo,
    tolerancia_segundos,
    indice_atual,
    direcao,
):
    esquerda = np.searchsorted(
        timestamps,
        timestamp_alvo - tolerancia_segundos,
        side="left",
    )

    direita = np.searchsorted(
        timestamps,
        timestamp_alvo + tolerancia_segundos,
        side="right",
    )

    melhor = None
    menor_distancia = None

    for j in range(esquerda, direita):
        if j == indice_atual:
            continue

        if direcao == "passado" and j >= indice_atual:
            continue

        if direcao == "futuro" and j <= indice_atual:
            continue

        distancia = abs(
            int(timestamps[j]) - int(timestamp_alvo)
        )

        if menor_distancia is None or distancia < menor_distancia:
            menor_distancia = distancia
            melhor = j

    return melhor


def construir_features_v3(df, features):
    if df.empty:
        raise RuntimeError("Histórico vazio.")

    df = (
        df.sort_values("timestamp")
        .drop_duplicates("timestamp")
        .reset_index(drop=True)
    )

    timestamps = df["timestamp"].to_numpy()
    niveis = df["water_level"].to_numpy()

    i = len(df) - 1
    timestamp_atual = int(timestamps[i])
    nivel_atual = float(niveis[i])

    tol = TOLERANCIA_LAG_MIN * 60

    indices = {}

    for nome, minutos in {
        "water_level_lag_1": 5,
        "water_level_lag_3": 15,
        "water_level_lag_6": 30,
    }.items():
        alvo = timestamp_atual - minutos * 60

        idx = buscar_leitura_proxima(
            timestamps,
            alvo,
            tol,
            i,
            "passado",
        )

        if idx is None:
            raise RuntimeError(
                f"Não foi encontrada leitura real para {minutos} "
                f"minutos atrás dentro da tolerância de "
                f"{TOLERANCIA_LAG_MIN} minutos."
            )

        indices[nome] = idx

    nivel_5 = float(niveis[indices["water_level_lag_1"]])
    nivel_15 = float(niveis[indices["water_level_lag_3"]])
    nivel_30 = float(niveis[indices["water_level_lag_6"]])

    delta_5 = nivel_atual - nivel_5
    delta_15 = nivel_atual - nivel_15
    delta_30 = nivel_atual - nivel_30

    trend_5 = delta_5 / 5.0
    trend_15 = delta_15 / 15.0
    trend_30 = delta_30 / 30.0

    acceleration = trend_5 - trend_15

    mean_15 = float(
        np.mean([nivel_15, nivel_5, nivel_atual])
    )

    mean_30 = float(
        np.mean([nivel_30, nivel_15, nivel_5, nivel_atual])
    )

    range_30 = float(
        max(nivel_30, nivel_15, nivel_5, nivel_atual)
        - min(nivel_30, nivel_15, nivel_5, nivel_atual)
    )

    linha = {
        "water_level": nivel_atual,
        "water_level_lag_1": nivel_5,
        "water_level_lag_3": nivel_15,
        "water_level_lag_6": nivel_30,
        "delta_5min": delta_5,
        "delta_15min": delta_15,
        "delta_30min": delta_30,
        "trend_5min": trend_5,
        "trend_15min": trend_15,
        "trend_30min": trend_30,
        "acceleration_trend": acceleration,
        "mean_15min": mean_15,
        "mean_30min": mean_30,
        "range_30min": range_30,
    }

    faltantes = [
        feature for feature in features
        if feature not in linha
    ]

    if faltantes:
        raise RuntimeError(
            "O modelo exige features que o construtor não conseguiu "
            f"calcular: {faltantes}"
        )

    return pd.DataFrame(
        [[linha[feature] for feature in features]],
        columns=features,
    ), linha, timestamp_atual


def prever_nivel_60min():
    pacote = carregar_modelo()

    modelo = pacote["modelo"]
    features = pacote["features"]

    df, path_usado = buscar_historico_operacional()

    X, dados_atual, timestamp = construir_features_v3(
        df,
        features,
    )

    previsao = float(modelo.predict(X)[0])

    return {
        "sensor_id": SENSOR_ID,
        "timestamp": timestamp,
        "nivel_atual_cm": round(
            float(dados_atual["water_level"]),
            2,
        ),
        "previsao_60min_cm": round(previsao, 2),
        "features_modelo": features,
        "feature_version": pacote.get(
            "feature_version",
            "desconhecida",
        ),
        "feature_set": pacote.get(
            "feature_set",
            "desconhecido",
        ),
        "historico_usado": path_usado,
    }


def main():
    print("=" * 70)
    print("FLOODSENSE AI - PREVISÃO V3.1")
    print("=" * 70)

    resultado = prever_nivel_60min()

    print()
    print(f"Sensor: {resultado['sensor_id']}")
    print(f"Nível atual: {resultado['nivel_atual_cm']:.2f} cm")
    print(
        f"Previsão para +60 min: "
        f"{resultado['previsao_60min_cm']:.2f} cm"
    )
    print(f"Feature set: {resultado['feature_set']}")
    print(f"Histórico: {resultado['historico_usado']}")
    print()
    print("Features usadas:")
    for feature in resultado["features_modelo"]:
        print(f"  - {feature}")


if __name__ == "__main__":
    main()