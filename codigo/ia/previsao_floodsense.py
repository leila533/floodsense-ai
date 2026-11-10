import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import os
import requests
import numpy as np
import pandas as pd
import joblib


# ============================================================
# FLOODSENSE AI - SERVIÇO DE PREVISÃO V4 PROGRESSIVO
#
# Carrega o pacote de modelos progressivos gerado por
# treinar_modelo_real_esp32_v4_progressivo.py e, a cada ciclo:
#
#   1. busca o histórico no Firebase;
#   2. descobre quais lags REAIS existem (por timestamp, ±2 min);
#   3. escolhe o modelo mais completo que pode ser alimentado:
#        FULL > LAG_15 > LAG_5 > STARTUP
#   4. monta as features SOMENTE com valores reais;
#   5. gera a previsão de +60 min;
#   6. publica em /ai_predictions/FS-001;
#   7. espera e repete.
#
# Nenhuma feature ausente é preenchida (sem zero, NaN, média,
# cópia da última leitura, interpolação ou valor estimado).
# Lags, tolerância e features vêm do próprio .pkl, garantindo
# coerência com o treinamento.
# ============================================================


PASTA_CODIGO = Path(__file__).resolve().parent.parent

FIREBASE_HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
SENSOR_ID = "FS-001"

MODEL_PATH = PASTA_CODIGO / "floodsense_modelos_progressivos_60min_esp32.pkl"

# Histórico de leitura atual do sensor.
# O firmware de operação deve gravar aqui.
HISTORY_PATHS = [
    f"/sensor_history/{SENSOR_ID}.json",
    f"/sensor_history_treinamento/{SENSOR_ID}.json",
]

PREDICTION_PATH = f"/ai_predictions/{SENSOR_ID}.json"

ORDEM_PRIORIDADE_PADRAO = ["FULL", "LAG_15", "LAG_5", "STARTUP"]

INTERVALO_CICLO_SEGUNDOS = 60

# Se a leitura mais recente for mais antiga que isso, o ESP32 provavelmente
# está desligado: prever +60 min a partir de uma leitura velha seria inválido.
MAX_IDADE_LEITURA_MIN = 15

# ------------------------------------------------------------
# STATUS (normal / atenção / alerta ...)
# Os limites NÃO estavam nos arquivos enviados e não foram inventados.
# Cole aqui a mesma regra do serviço anterior. Enquanto estiver None,
# o campo "status" NÃO é enviado e o Firebase mantém o valor anterior.
# ------------------------------------------------------------
STATUS_LIMITES_CM = None


def calcular_status(nivel_previsto_cm):
    if STATUS_LIMITES_CM is None:
        return None
    raise NotImplementedError(
        "Implemente aqui a regra de status usada pelo dashboard."
    )


class LeituraAntigaError(RuntimeError):
    pass


def log(msg):
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{agora}] {msg}", flush=True)


# ============================================================
# MODELO
# ============================================================

_CACHE_MODELO = {"mtime": None, "pacote": None}


def carregar_modelo():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {MODEL_PATH}")

    mtime = MODEL_PATH.stat().st_mtime

    # Só recarrega do disco se o arquivo mudou (ex.: novo treinamento).
    if _CACHE_MODELO["pacote"] is not None and _CACHE_MODELO["mtime"] == mtime:
        return _CACHE_MODELO["pacote"]

    pacote = joblib.load(MODEL_PATH)

    if not isinstance(pacote, dict) or "modelos" not in pacote:
        raise RuntimeError(
            "O arquivo não é um pacote de modelos progressivos "
            "(falta a chave 'modelos'). Rode o treinamento V4."
        )

    if not pacote["modelos"]:
        raise RuntimeError("O pacote não contém nenhum modelo treinado.")

    for nome, cfg in pacote["modelos"].items():
        if "modelo" not in cfg or "features" not in cfg:
            raise RuntimeError(
                f"Modelo {nome} incompatível: faltam 'modelo' ou 'features'."
            )

    if "lags_minutos" not in pacote or "tolerancia_lag_min" not in pacote:
        raise RuntimeError(
            "Pacote sem 'lags_minutos' ou 'tolerancia_lag_min'."
        )

    _CACHE_MODELO["mtime"] = mtime
    _CACHE_MODELO["pacote"] = pacote

    log(
        "Pacote carregado. Modelos disponíveis: "
        + ", ".join(pacote["modelos"].keys())
    )

    return pacote


# ============================================================
# FIREBASE
# ============================================================

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
            nivel = float(nivel)
            if not np.isfinite(nivel):
                continue

            registros.append({
                "timestamp": int(timestamp),
                "water_level": nivel,
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
    Tenta primeiro o histórico operacional.
    Se estiver vazio, usa o histórico de treinamento.
    """
    for path in HISTORY_PATHS:
        df = buscar_historico(path)

        if not df.empty:
            return df, path

    raise RuntimeError(
        "Nenhuma leitura encontrada no Firebase. "
        "Verifique se o ESP32 está gravando o histórico."
    )


from carregar_segredos import carregar as _carregar_segredos
_carregar_segredos()


def login_dispositivo():
    """Login do dispositivo (mesma conta usada pelo ESP32). Necessário para escrever no Firebase."""
    api_key = os.environ.get("FS_API_KEY")
    email = os.environ.get("FS_DEVICE_EMAIL")
    senha = os.environ.get("FS_DEVICE_PASSWORD")
    if not (api_key and email and senha):
        raise RuntimeError("Defina FS_API_KEY, FS_DEVICE_EMAIL e FS_DEVICE_PASSWORD antes de rodar.")
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    r = requests.post(url, json={"email": email, "password": senha, "returnSecureToken": True}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Falha no login do dispositivo: HTTP {r.status_code}")
    return r.json()["idToken"]


def publicar_previsao(payload):
    token = login_dispositivo()
    url = f"{FIREBASE_HOST}{PREDICTION_PATH}?auth={token}"
    # PATCH atualiza só os campos enviados e não apaga os demais.
    resposta = requests.patch(url, json=payload, timeout=20)
    resposta.raise_for_status()


# ============================================================
# LOCALIZAÇÃO DE LEITURA REAL (idêntica ao treinamento)
# ============================================================

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


# ============================================================
# FEATURES REAIS DISPONÍVEIS
# ============================================================

def coletar_features_disponiveis(df, pacote):
    """
    Retorna somente o que existe de verdade:
      - water_level (leitura atual = última do histórico)
      - cada lag encontrado dentro da tolerância, no PASSADO da leitura atual

    Lags não encontrados simplesmente NÃO entram no dicionário.
    """
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

    if not np.isfinite(nivel_atual):
        raise RuntimeError("Leitura atual inválida.")

    tol = int(pacote["tolerancia_lag_min"]) * 60

    valores = {"water_level": nivel_atual}
    lags_encontrados = []

    for nome, minutos in pacote["lags_minutos"].items():
        alvo = timestamp_atual - int(minutos) * 60

        idx = buscar_leitura_proxima(
            timestamps,
            alvo,
            tol,
            i,
            "passado",
        )

        if idx is None:
            continue

        valores[nome] = float(niveis[idx])
        lags_encontrados.append((int(minutos), nome))

    lags_encontrados.sort()

    return valores, [f"{m}min" for m, _ in lags_encontrados], timestamp_atual


def escolher_modelo(pacote, valores):
    """
    Percorre do mais completo ao mais simples e devolve o primeiro
    cujas features existem TODAS em 'valores'.
    """
    ordem = pacote.get("ordem_prioridade") or ORDEM_PRIORIDADE_PADRAO

    for nome in ordem:
        cfg = pacote["modelos"].get(nome)

        if cfg is None:
            continue

        if all(feature in valores for feature in cfg["features"]):
            return nome, cfg

    raise RuntimeError(
        "Nenhum modelo progressivo pôde ser alimentado com as "
        "leituras disponíveis."
    )


# ============================================================
# PREVISÃO
# ============================================================

def prever_com_historico(pacote, df, historico_usado="", checar_idade=True):
    valores, lags_disponiveis, timestamp = coletar_features_disponiveis(
        df,
        pacote,
    )

    if checar_idade:
        idade_min = (time.time() - timestamp) / 60.0

        if idade_min > MAX_IDADE_LEITURA_MIN:
            raise LeituraAntigaError(
                f"Última leitura tem {idade_min:.1f} min "
                f"(limite {MAX_IDADE_LEITURA_MIN} min). "
                "ESP32 provavelmente desligado; previsão não gerada."
            )

    modo, cfg = escolher_modelo(pacote, valores)

    features = cfg["features"]

    X = pd.DataFrame(
        [[valores[feature] for feature in features]],
        columns=features,
    )

    previsao = float(cfg["modelo"].predict(X)[0])

    return {
        "sensor_id": SENSOR_ID,
        "timestamp": timestamp,
        "nivel_atual_cm": round(float(valores["water_level"]), 2),
        "previsao_60min_cm": round(previsao, 2),
        "prediction_mode": modo,
        "available_lags": lags_disponiveis,
        "features_modelo": list(features),
        "valores_features": {f: valores[f] for f in features},
        "model_algorithm": cfg.get("algoritmo", "desconhecido"),
        "model_class": cfg.get("algoritmo_classe", "desconhecido"),
        "model_version": cfg.get("versao_modelo", "desconhecida"),
        "feature_version": cfg.get("feature_version", "desconhecida"),
        "feature_set": cfg.get("feature_set", modo),
        "historico_usado": historico_usado,
    }


def prever_nivel_60min(checar_idade=True):
    pacote = carregar_modelo()
    df, path_usado = buscar_historico_operacional()

    return prever_com_historico(
        pacote,
        df,
        historico_usado=path_usado,
        checar_idade=checar_idade,
    )


def montar_payload_firebase(resultado):
    classe = str(resultado["model_class"]).replace("Regressor", "")

    payload = {
        # Campos já usados pelo dashboard
        "current_level_cm": resultado["nivel_atual_cm"],
        "predicted_level_60min_cm": resultado["previsao_60min_cm"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_minutes": 60,
        "model": classe,
        "sensor_unit": "cm",
        "real_sensor_compatible": True,

        # Novos campos dos modelos progressivos
        "prediction_mode": resultado["prediction_mode"],
        "available_lags": resultado["available_lags"],
        "model_algorithm": resultado["model_algorithm"],
        "model_version": resultado["model_version"],
        "sensor_id": resultado["sensor_id"],
        "reading_timestamp": resultado["timestamp"],
    }

    status = calcular_status(resultado["previsao_60min_cm"])
    if status is not None:
        payload["status"] = status

    return payload


def ciclo_seguro(checar_idade=True):
    """
    Um ciclo completo. Nunca levanta exceção: qualquer erro de Firebase,
    de histórico insuficiente ou de modelo é registrado e o serviço
    tenta de novo no próximo ciclo.
    """
    try:
        resultado = prever_nivel_60min(checar_idade=checar_idade)
        payload = montar_payload_firebase(resultado)
        publicar_previsao(payload)

        log(
            f"[{resultado['prediction_mode']}] "
            f"atual={resultado['nivel_atual_cm']:.2f} cm | "
            f"+60min={resultado['previsao_60min_cm']:.2f} cm | "
            f"lags={resultado['available_lags']} | "
            f"algoritmo={resultado['model_algorithm']}"
        )

        return resultado

    except LeituraAntigaError as erro:
        log(f"AVISO: {erro}")
    except Exception as erro:
        log(f"ERRO neste ciclo ({type(erro).__name__}): {erro}")

    return None


def main():
    parser = argparse.ArgumentParser(
        description="FloodSense AI - serviço de previsão progressivo"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="executa um único ciclo e sai",
    )
    parser.add_argument(
        "--intervalo",
        type=int,
        default=INTERVALO_CICLO_SEGUNDOS,
        help="segundos entre ciclos (padrão: %(default)s)",
    )
    parser.add_argument(
        "--sem-checagem-idade",
        action="store_true",
        help="não recusa leituras antigas (útil para testar com histórico antigo)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("FLOODSENSE AI - PREVISÃO V4 PROGRESSIVA")
    print("=" * 70)

    if STATUS_LIMITES_CM is None:
        log(
            "AVISO: regra de status não configurada; o campo 'status' "
            "não será atualizado."
        )

    checar_idade = not args.sem_checagem_idade

    if args.once:
        ciclo_seguro(checar_idade)
        return

    while True:
        ciclo_seguro(checar_idade)
        time.sleep(args.intervalo)


if __name__ == "__main__":
    main()