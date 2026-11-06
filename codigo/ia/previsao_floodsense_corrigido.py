import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

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
#   3. entre os modelos que PODEM ser alimentados com as leituras
#      reais, escolhe o de menor MAE de teste final (métrica gravada
#      no próprio .pkl); STARTUP é só fallback inicial, usado quando
#      nenhum modelo com lags pode ser alimentado;
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
    f"/sensor_history_treinamento/{SENSOR_ID}.json",
]

PREDICTION_PATH = f"/ai_predictions/{SENSOR_ID}.json"

ORDEM_PRIORIDADE_PADRAO = ["FULL", "LAG_15", "LAG_5", "STARTUP"]

INTERVALO_CICLO_SEGUNDOS = 300

# Se a leitura mais recente for mais antiga que isso, o ESP32 provavelmente
# está desligado: prever +60 min a partir de uma leitura velha seria inválido.
MAX_IDADE_LEITURA_MIN = 15

# ------------------------------------------------------------
# Limites usados pelo dashboard FloodSense AI:
# normal < 60 cm; warning de 60 a menos de 90 cm; critical >= 90 cm.
# Se o dashboard tiver rótulos diferentes, mantenha os nomes esperados por ele.
# ------------------------------------------------------------
STATUS_LIMITES_CM = {"warning": 60.0, "critical": 90.0}


def calcular_status(nivel_previsto_cm):
    nivel = float(nivel_previsto_cm)
    if not np.isfinite(nivel):
        raise ValueError("Nível previsto não é finito; status não pode ser calculado.")
    if nivel >= STATUS_LIMITES_CM["critical"]:
        return "critical"
    if nivel >= STATUS_LIMITES_CM["warning"]:
        return "warning"
    return "normal"


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

    horizonte = pacote.get("horizonte_minutos", pacote.get("horizon_minutes", 60))
    try:
        horizonte = int(horizonte)
    except (TypeError, ValueError) as erro:
        raise RuntimeError("Metadado de horizonte inválido no pacote do modelo.") from erro
    if horizonte != 60:
        raise RuntimeError(
            f"Horizonte incompatível: o serviço publica previsão +60 min, "
            f"mas o pacote informa {horizonte} min."
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
    # Não transformar erros HTTP (401/403/500 etc.) em histórico vazio:
    # isso esconderia problemas de autenticação ou indisponibilidade.
    resposta.raise_for_status()
    dados = resposta.json()

    if dados is None:
        return pd.DataFrame(columns=["timestamp", "water_level"])
    if not isinstance(dados, dict):
        raise ValueError(f"Formato inesperado no histórico Firebase: {type(dados).__name__}")

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
    Lê o histórico atual do ESP32 em HISTORY_PATHS (hoje, somente
    /sensor_history_treinamento/FS-001.json). NÃO há fallback para
    /sensor_history: se não houver leituras válidas aqui, o ciclo falha
    com mensagem clara e tenta de novo no próximo.
    """
    for path in HISTORY_PATHS:
        df = buscar_historico(path)

        if not df.empty:
            return df, path

    raise RuntimeError(
        "Nenhuma leitura encontrada no Firebase. "
        "Verifique se o ESP32 está gravando o histórico."
    )


def publicar_previsao(payload):
    url = f"{FIREBASE_HOST}{PREDICTION_PATH}"

    # PATCH atualiza só os campos enviados e não apaga os demais
    # campos que o dashboard possa estar lendo.
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


def _metricas_validas(cfg):
    """
    Devolve (mae, rmse) do teste final gravado no pacote, ou None se o
    MAE não for um número finito. RMSE ausente vira +inf (só afeta o
    desempate).
    """
    metricas = cfg.get("metricas_teste") or {}

    try:
        mae = float(metricas.get("mae"))
    except (TypeError, ValueError):
        return None

    if not np.isfinite(mae):
        return None

    try:
        rmse = float(metricas.get("rmse"))
    except (TypeError, ValueError):
        rmse = np.inf

    if not np.isfinite(rmse):
        rmse = np.inf

    return mae, rmse


def _eh_fallback_inicial(nome, cfg):
    return nome == "STARTUP" or list(cfg["features"]) == ["water_level"]


def escolher_modelo(pacote, valores):
    """
    1. Considera apenas modelos cujas features existem TODAS em 'valores'.
    2. Entre os que usam lags, escolhe o de menor MAE de teste final
       (desempate: menor RMSE; depois a ordem de prioridade do pacote).
       Modelo sem métrica válida nunca vence um com métrica válida.
    3. STARTUP só é usado quando nenhum modelo com lags pode ser
       alimentado (fallback inicial).

    Retorna (nome, cfg, selecao).
    """
    ordem = list(pacote.get("ordem_prioridade") or ORDEM_PRIORIDADE_PADRAO)
    nomes = ordem + [n for n in pacote["modelos"] if n not in ordem]

    alimentaveis = []

    for pos, nome in enumerate(nomes):
        cfg = pacote["modelos"].get(nome)

        if cfg is None:
            continue

        if all(feature in valores for feature in cfg["features"]):
            alimentaveis.append((pos, nome, cfg))

    if not alimentaveis:
        raise RuntimeError(
            "Nenhum modelo progressivo pôde ser alimentado com as "
            "leituras disponíveis."
        )

    com_lags = [
        item for item in alimentaveis
        if not _eh_fallback_inicial(item[1], item[2])
    ]

    fallback_inicial = not com_lags
    pool = alimentaveis if fallback_inicial else com_lags

    def chave(item):
        pos, _, cfg = item
        metricas = _metricas_validas(cfg)

        if metricas is None:
            return (1, np.inf, np.inf, pos)

        return (0, metricas[0], metricas[1], pos)

    ranking = sorted(pool, key=chave)

    # Se há modelos com lags disponíveis, mas nenhum tem MAE válido,
    # não selecionar arbitrariamente um modelo sem base de comparação.
    if not fallback_inicial and all(_metricas_validas(item[2]) is None for item in ranking):
        raise RuntimeError(
            "Há modelos com lags alimentáveis, mas nenhum possui MAE de teste válido. "
            "Revise o pacote de treinamento antes de publicar previsões."
        )

    _, nome, cfg = ranking[0]
    metricas = _metricas_validas(cfg)

    if fallback_inicial:
        metrica = "fallback_inicial"
        motivo = (
            "fallback inicial: nenhum modelo com lags pôde ser alimentado"
        )
    elif metricas is None:
        metrica = "sem_metricas_validas"
        motivo = "nenhum modelo alimentável possui métricas de teste válidas"
    elif len(ranking) == 1:
        metrica = "mae_test"
        motivo = "único modelo com lags alimentável"
    else:
        metrica = "mae_test"
        motivo = "menor MAE entre modelos alimentáveis"

        segundo = _metricas_validas(ranking[1][2])
        if segundo is not None and segundo[0] == metricas[0]:
            motivo = "empate no MAE; menor RMSE entre modelos alimentáveis"

    baseline = (cfg.get("metricas_teste") or {}).get("baseline_mae")
    melhoria = (cfg.get("metricas_teste") or {}).get("melhoria_mae_percent")

    selecao = {
        "modelos_considerados": [item[1] for item in ranking],
        "escolhido": nome,
        "metrica": metrica,
        "mae_teste_cm": metricas[0] if metricas is not None else None,
        "baseline_mae_cm": baseline,
        "melhoria_mae_percent": melhoria,
        "motivo": motivo,
        "fallback_inicial": fallback_inicial,
    }

    return nome, cfg, selecao


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

        if idade_min < -1.0:
            raise ValueError(
                f"Timestamp da última leitura está no futuro ({abs(idade_min):.1f} min). "
                "Verifique o relógio/timestamp enviado pelo ESP32."
            )

        if idade_min > MAX_IDADE_LEITURA_MIN:
            raise LeituraAntigaError(
                f"Última leitura tem {idade_min:.1f} min "
                f"(limite {MAX_IDADE_LEITURA_MIN} min). "
                "ESP32 provavelmente desligado; previsão não gerada."
            )

    modo, cfg, selecao = escolher_modelo(pacote, valores)

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
        "selecao": selecao,
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

        # Critério de seleção (demonstra por que este modelo foi usado)
        "selection_metric": resultado["selecao"]["metrica"],
        "selection_mae_test_cm": resultado["selecao"]["mae_teste_cm"],
        "initial_fallback": resultado["selecao"]["fallback_inicial"],
    }

    status = calcular_status(resultado["previsao_60min_cm"])
    if status is not None:
        payload["status"] = status

    return payload


def registrar_selecao(selecao):
    mae = selecao["mae_teste_cm"]

    log(
        "[SELEÇÃO] modelos disponíveis: "
        + ", ".join(selecao["modelos_considerados"])
    )
    log(f"[SELEÇÃO] escolhido: {selecao['escolhido']}")
    log(
        "[SELEÇÃO] MAE teste: "
        + (f"{mae:.4f} cm" if mae is not None else "indisponível")
    )
    log(f"[SELEÇÃO] motivo: {selecao['motivo']}")

    if selecao["fallback_inicial"]:
        baseline = selecao.get("baseline_mae_cm")
        melhoria = selecao.get("melhoria_mae_percent")

        detalhe = ""
        if baseline is not None and melhoria is not None:
            detalhe = (
                f" (baseline MAE {float(baseline):.2f} cm, "
                f"melhoria {float(melhoria):.2f}%)"
            )

        log(
            "[SELEÇÃO] AVISO: STARTUP é um FALLBACK INICIAL, não o "
            f"melhor modelo{detalhe}."
        )


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

        registrar_selecao(resultado["selecao"])

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
        resultado = ciclo_seguro(checar_idade)
        return 0 if resultado is not None else 1

    while True:
        ciclo_seguro(checar_idade)
        time.sleep(max(1, args.intervalo))


if __name__ == "__main__":
    try:
        resultado_main = main()
        if isinstance(resultado_main, int):
            raise SystemExit(resultado_main)
    except KeyboardInterrupt:
        log("Serviço interrompido pelo usuário (Ctrl+C).")
        raise SystemExit(0)