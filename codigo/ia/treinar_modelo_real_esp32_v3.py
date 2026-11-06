from pathlib import Path

import requests
import pandas as pd
import numpy as np
import joblib

from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit


# ============================================================
# FLOODSENSE AI - V3
# TREINAMENTO REAL DO ESP32 - PREVISÃO DE 60 MINUTOS
#
# Usa somente dados reais já coletados.
# Não interpola, não inventa e não exige nova coleta.
#
# V3 adiciona características de tendência calculadas a partir
# das leituras reais:
#   - variações de 5, 15 e 30 min
#   - velocidades de subida/descida
#   - aceleração da tendência
#   - média e amplitude dos últimos 30 min
#
# O modelo escolhido é validado temporalmente antes de ser
# treinado novamente com 100% das amostras válidas.
# ============================================================


# ============================================================
# 1. CONFIGURAÇÕES
# ============================================================

PASTA_CODIGO = Path(__file__).resolve().parent.parent

FIREBASE_HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
SENSOR_ID = "FS-001"

HISTORY_PATH = f"/sensor_history_treinamento/{SENSOR_ID}.json"

MODEL_PATH = PASTA_CODIGO / "floodsense_model_60min_esp32.pkl"
MODEL_PATH_COMPAT = PASTA_CODIGO / "floodsense_model_real_esp32_60min.pkl"

RESULTS_PATH = PASTA_CODIGO / "resultados_modelo_real_esp32_60min.csv"
IMPORTANCE_PATH = PASTA_CODIGO / "importancia_variaveis_real_esp32.csv"
SUMMARY_PATH = PASTA_CODIGO / "resumo_modelo_real_esp32.csv"
FULL_HISTORY_PATH = PASTA_CODIGO / "historico_completo_esp32.csv"
DATASET_PATH = PASTA_CODIGO / "dataset_temporal_60min_real.csv"
SEARCH_PATH = PASTA_CODIGO / "comparacao_modelos_v3.csv"

TOLERANCIA_LAG_MIN = 2
HORIZONTE_MINUTOS = 60
TOLERANCIA_HORIZONTE_MIN = 2

LAGS_MINUTOS = {
    "water_level_lag_1": 5,
    "water_level_lag_3": 15,
    "water_level_lag_6": 30,
}

CORE_FEATURES = [
    "water_level",
    "water_level_lag_1",
    "water_level_lag_3",
    "water_level_lag_6",
]

TREND_FEATURES = [
    "delta_5min",
    "delta_15min",
    "delta_30min",
    "trend_5min",
    "trend_15min",
    "trend_30min",
    "acceleration_trend",
]

CONTEXT_FEATURES = [
    "mean_15min",
    "mean_30min",
    "range_30min",
]

FEATURE_SETS = {
    "CORE": CORE_FEATURES,
    "CORE_TENDENCIA": CORE_FEATURES + TREND_FEATURES,
    "CORE_TENDENCIA_CONTEXTO": CORE_FEATURES + TREND_FEATURES + CONTEXT_FEATURES,
}

TARGET = "target_60min"


# ============================================================
# 2. HISTÓRICO
# ============================================================

def buscar_historico():
    url = f"{FIREBASE_HOST}{HISTORY_PATH}"

    print("\n" + "=" * 70)
    print("FLOODSENSE AI V3 - BUSCANDO HISTÓRICO REAL")
    print("=" * 70)
    print(f"Sensor: {SENSOR_ID}")
    print(f"URL: {url}")

    resposta = requests.get(url, timeout=30)
    print(f"HTTP: {resposta.status_code}")
    resposta.raise_for_status()

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
        raise RuntimeError("Nenhum registro válido encontrado no Firebase.")

    df = pd.DataFrame(registros)
    df = (
        df.drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# 3. LOCALIZAÇÃO DE LEITURA REAL
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

    melhor_indice = None
    melhor_distancia = None

    for j in range(esquerda, direita):
        if j == indice_atual:
            continue

        if direcao == "passado" and j >= indice_atual:
            continue

        if direcao == "futuro" and j <= indice_atual:
            continue

        distancia = abs(int(timestamps[j]) - int(timestamp_alvo))

        if melhor_distancia is None or distancia < melhor_distancia:
            melhor_distancia = distancia
            melhor_indice = j

    return melhor_indice


# ============================================================
# 4. DATASET + ENGENHARIA DE FEATURES
# ============================================================

def criar_dataset(df):
    print("\n" + "=" * 70)
    print("CRIANDO DATASET TEMPORAL V3")
    print("=" * 70)

    dados = (
        df.copy()
        .sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"])
        .reset_index(drop=True)
    )

    timestamps = dados["timestamp"].to_numpy()
    niveis = dados["water_level"].to_numpy()

    tol_lag = TOLERANCIA_LAG_MIN * 60
    tol_futuro = TOLERANCIA_HORIZONTE_MIN * 60

    linhas = []
    sem_lag = 0
    sem_futuro = 0

    for i in range(len(dados)):
        atual = int(timestamps[i])

        indices_lag = {}

        ok = True
        for nome, minutos in LAGS_MINUTOS.items():
            alvo = atual - minutos * 60
            idx = buscar_leitura_proxima(
                timestamps,
                alvo,
                tol_lag,
                i,
                "passado",
            )

            if idx is None:
                ok = False
                break

            indices_lag[nome] = idx

        if not ok:
            sem_lag += 1
            continue

        alvo_futuro = atual + HORIZONTE_MINUTOS * 60

        idx_futuro = buscar_leitura_proxima(
            timestamps,
            alvo_futuro,
            tol_futuro,
            i,
            "futuro",
        )

        if idx_futuro is None:
            sem_futuro += 1
            continue

        diferenca_futura = (
            timestamps[idx_futuro] - timestamps[i]
        ) / 60.0

        if not (
            HORIZONTE_MINUTOS - TOLERANCIA_HORIZONTE_MIN
            <= diferenca_futura
            <= HORIZONTE_MINUTOS + TOLERANCIA_HORIZONTE_MIN
        ):
            continue

        atual_nivel = float(niveis[i])
        nivel_5 = float(niveis[indices_lag["water_level_lag_1"]])
        nivel_15 = float(niveis[indices_lag["water_level_lag_3"]])
        nivel_30 = float(niveis[indices_lag["water_level_lag_6"]])

        delta_5 = atual_nivel - nivel_5
        delta_15 = atual_nivel - nivel_15
        delta_30 = atual_nivel - nivel_30

        trend_5 = delta_5 / 5.0
        trend_15 = delta_15 / 15.0
        trend_30 = delta_30 / 30.0

        acceleration = trend_5 - trend_15

        mean_15 = float(np.mean([nivel_15, nivel_5, atual_nivel]))
        mean_30 = float(np.mean([nivel_30, nivel_15, nivel_5, atual_nivel]))

        range_30 = float(
            max(nivel_30, nivel_15, nivel_5, atual_nivel)
            - min(nivel_30, nivel_15, nivel_5, atual_nivel)
        )

        linhas.append({
            "timestamp": int(timestamps[i]),
            "water_level": atual_nivel,
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
            "target_60min": float(niveis[idx_futuro]),
            "intervalo_futuro_min": float(diferenca_futura),
        })

    dataset = pd.DataFrame(linhas)

    print(f"Registros originais: {len(df)}")
    print(f"Descartados por falta de lag: {sem_lag}")
    print(f"Descartados por falta de futuro +60 min: {sem_futuro}")
    print(f"Amostras temporais válidas: {len(dataset)}")

    if dataset.empty:
        raise RuntimeError(
            "Nenhuma amostra temporal válida foi encontrada."
        )

    dataset = dataset.sort_values("timestamp").reset_index(drop=True)

    return dataset


# ============================================================
# 5. DIAGNÓSTICO
# ============================================================

def diagnostico(df, dataset):
    print("\n" + "=" * 70)
    print("DIAGNÓSTICO")
    print("=" * 70)

    if len(df) > 1:
        intervalos = df["timestamp"].diff().dropna() / 60.0
        print(f"Intervalo médio: {intervalos.mean():.2f} min")
        print(f"Intervalo mínimo: {intervalos.min():.2f} min")
        print(f"Intervalo máximo: {intervalos.max():.2f} min")

        recentes = intervalos.tail(30)
        print(
            f"Últimos 30: mediana={recentes.median():.2f} | "
            f"mínimo={recentes.min():.2f} | máximo={recentes.max():.2f}"
        )

    print(
        f"Nível atual: min={dataset['water_level'].min():.1f} | "
        f"máx={dataset['water_level'].max():.1f} | "
        f"média={dataset['water_level'].mean():.1f}"
    )

    print(
        f"Nível +60: min={dataset['target_60min'].min():.1f} | "
        f"máx={dataset['target_60min'].max():.1f} | "
        f"média={dataset['target_60min'].mean():.1f}"
    )


# ============================================================
# 6. MODELOS CANDIDATOS
# ============================================================

def criar_modelos():
    return {
        "RF_700_depthNone_leaf1": RandomForestRegressor(
            n_estimators=700,
            max_depth=None,
            min_samples_leaf=1,
            max_features=1.0,
            random_state=42,
            n_jobs=-1,
        ),
        "RF_500_depth12_leaf1": RandomForestRegressor(
            n_estimators=500,
            max_depth=12,
            min_samples_leaf=1,
            max_features=1.0,
            random_state=42,
            n_jobs=-1,
        ),
        "RF_700_depth16_leaf1": RandomForestRegressor(
            n_estimators=700,
            max_depth=16,
            min_samples_leaf=1,
            max_features=1.0,
            random_state=42,
            n_jobs=-1,
        ),
        "ET_700_depthNone_leaf1": ExtraTreesRegressor(
            n_estimators=700,
            max_depth=None,
            min_samples_leaf=1,
            max_features=1.0,
            random_state=42,
            n_jobs=-1,
        ),
        "GBR_400_depth3_leaf2": GradientBoostingRegressor(
            n_estimators=400,
            learning_rate=0.03,
            max_depth=3,
            min_samples_leaf=2,
            loss="huber",
            random_state=42,
        ),
    }


# ============================================================
# 7. OTIMIZAÇÃO TEMPORAL
# ============================================================

def otimizar(dataset, desenvolvimento):
    print("\n" + "=" * 70)
    print("OTIMIZAÇÃO TEMPORAL V3")
    print("=" * 70)

    tscv = TimeSeriesSplit(n_splits=4)
    resultados = []

    for nome_features, features in FEATURE_SETS.items():
        X = desenvolvimento[features]
        y = desenvolvimento[TARGET]

        for nome_modelo, modelo_base in criar_modelos().items():
            maes = []
            rmses = []
            r2s = []

            print(f"\nTestando: {nome_features} + {nome_modelo}")

            for fold, (train_idx, val_idx) in enumerate(tscv.split(X), start=1):
                modelo = modelo_base.__class__(**modelo_base.get_params())

                X_train = X.iloc[train_idx]
                X_val = X.iloc[val_idx]
                y_train = y.iloc[train_idx]
                y_val = y.iloc[val_idx]

                modelo.fit(X_train, y_train)
                pred = modelo.predict(X_val)

                mae = mean_absolute_error(y_val, pred)
                rmse = np.sqrt(mean_squared_error(y_val, pred))
                r2 = r2_score(y_val, pred)

                maes.append(mae)
                rmses.append(rmse)
                r2s.append(r2)

                print(
                    f"  Fold {fold}: "
                    f"MAE={mae:.3f} | "
                    f"RMSE={rmse:.3f} | "
                    f"R²={r2:.3f}"
                )

            media_mae = float(np.mean(maes))
            media_rmse = float(np.mean(rmses))
            media_r2 = float(np.mean(r2s))

            print(
                f"  MÉDIA: MAE={media_mae:.3f} | "
                f"RMSE={media_rmse:.3f} | "
                f"R²={media_r2:.3f}"
            )

            resultados.append({
                "feature_set": nome_features,
                "modelo": nome_modelo,
                "mae_cv": media_mae,
                "rmse_cv": media_rmse,
                "r2_cv": media_r2,
            })

    busca = pd.DataFrame(resultados)
    busca = busca.sort_values(
        ["mae_cv", "rmse_cv"],
        ascending=[True, True],
    ).reset_index(drop=True)

    melhor = busca.iloc[0]

    print("\n" + "=" * 70)
    print("MELHOR CONFIGURAÇÃO V3")
    print("=" * 70)
    print(f"Features: {melhor['feature_set']}")
    print(f"Modelo:   {melhor['modelo']}")
    print(f"MAE CV:   {melhor['mae_cv']:.4f} cm")
    print(f"RMSE CV:  {melhor['rmse_cv']:.4f} cm")
    print(f"R² CV:    {melhor['r2_cv']:.4f}")

    return busca, melhor


# ============================================================
# 8. TREINAMENTO
# ============================================================

def treinar():
    print("\n" + "=" * 70)
    print("FLOODSENSE AI V3")
    print("MODELO REAL DO ESP32 - PREVISÃO DE 60 MINUTOS")
    print("=" * 70)

    df = buscar_historico()

    df.to_csv(FULL_HISTORY_PATH, index=False)

    dataset = criar_dataset(df)
    diagnostico(df, dataset)

    dataset.to_csv(DATASET_PATH, index=False)

    if len(dataset) < 40:
        raise RuntimeError(
            f"Amostras temporais insuficientes: {len(dataset)}."
        )

    # 80% desenvolvimento / 20% teste final.
    corte = int(len(dataset) * 0.80)

    desenvolvimento = dataset.iloc[:corte].copy()
    teste_final = dataset.iloc[corte:].copy()

    print("\n" + "=" * 70)
    print("DIVISÃO TEMPORAL HONESTA")
    print("=" * 70)
    print(f"Desenvolvimento: {len(desenvolvimento)}")
    print(f"Teste final:     {len(teste_final)}")
    print("O teste final NÃO participa da escolha do modelo.")

    busca, melhor = otimizar(dataset, desenvolvimento)

    busca.to_csv(SEARCH_PATH, index=False)

    feature_set_name = str(melhor["feature_set"])
    model_name = str(melhor["modelo"])

    features = FEATURE_SETS[feature_set_name]
    modelo_base = criar_modelos()[model_name]

    # Treina somente no desenvolvimento para avaliação final.
    modelo_teste = modelo_base.__class__(**modelo_base.get_params())
    modelo_teste.fit(
        desenvolvimento[features],
        desenvolvimento[TARGET],
    )

    pred_teste = modelo_teste.predict(teste_final[features])

    mae = mean_absolute_error(teste_final[TARGET], pred_teste)
    rmse = np.sqrt(
        mean_squared_error(teste_final[TARGET], pred_teste)
    )
    r2 = r2_score(teste_final[TARGET], pred_teste)

    baseline = teste_final["water_level"].values

    baseline_mae = mean_absolute_error(
        teste_final[TARGET], baseline
    )
    baseline_rmse = np.sqrt(
        mean_squared_error(teste_final[TARGET], baseline)
    )
    baseline_r2 = r2_score(
        teste_final[TARGET], baseline
    )

    melhoria_mae = (
        (baseline_mae - mae) / baseline_mae * 100
        if baseline_mae else 0
    )
    melhoria_rmse = (
        (baseline_rmse - rmse) / baseline_rmse * 100
        if baseline_rmse else 0
    )

    print("\n" + "=" * 70)
    print("VALIDAÇÃO FINAL V3 - BLOCO MAIS RECENTE")
    print("=" * 70)
    print(f"Configuração: {feature_set_name} + {model_name}")
    print(f"MAE : {mae:.4f} cm")
    print(f"RMSE: {rmse:.4f} cm")
    print(f"R²  : {r2:.6f}")
    print()
    print(f"Baseline MAE : {baseline_mae:.4f} cm")
    print(f"Baseline RMSE: {baseline_rmse:.4f} cm")
    print(f"Baseline R²  : {baseline_r2:.6f}")
    print()
    print(f"Melhoria MAE : {melhoria_mae:.2f}%")
    print(f"Melhoria RMSE: {melhoria_rmse:.2f}%")

    # ========================================================
    # TREINAMENTO FINAL COM 100% DAS AMOSTRAS VÁLIDAS
    # ========================================================

    print("\n" + "=" * 70)
    print("TREINAMENTO FINAL V3 - 100% DOS DADOS TEMPORAIS VÁLIDOS")
    print("=" * 70)
    print(f"Treinando com {len(dataset)} amostras...")

    modelo_final = modelo_base.__class__(**modelo_base.get_params())
    modelo_final.fit(
        dataset[features],
        dataset[TARGET],
    )

    importancias = pd.DataFrame({
        "feature": features,
        "importance": modelo_final.feature_importances_
        if hasattr(modelo_final, "feature_importances_")
        else np.nan,
    }).sort_values(
        "importance",
        ascending=False,
    )

    importancias.to_csv(
        IMPORTANCE_PATH,
        index=False,
    )

    resultados = teste_final[
        ["timestamp", "water_level", "target_60min"]
    ].copy()

    resultados["nivel_previsto_60min_cm"] = pred_teste
    resultados["erro_absoluto_cm"] = np.abs(
        resultados["target_60min"]
        - resultados["nivel_previsto_60min_cm"]
    )

    resultados = resultados.rename(columns={
        "water_level": "nivel_atual_cm",
        "target_60min": "nivel_real_60min_cm",
    })

    resultados.to_csv(
        RESULTS_PATH,
        index=False,
    )

    pacote_modelo = {
        "modelo": modelo_final,
        "features": features,
        "feature_set": feature_set_name,
        "feature_version": "v3_tendencia",
        "target": TARGET,
        "horizonte_minutos": HORIZONTE_MINUTOS,
        "timestep_minutos": 1,
        "sensor_id": SENSOR_ID,
        "unidade": "cm",
        "origem_dados": "ESP32 + AJ-SR04M + Firebase",
        "history_path_treinamento": HISTORY_PATH,
        "lags_minutos": LAGS_MINUTOS,
        "tolerancia_lag_min": TOLERANCIA_LAG_MIN,
        "tolerancia_horizonte_min": TOLERANCIA_HORIZONTE_MIN,
        "metricas_teste": {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "baseline_mae": float(baseline_mae),
            "baseline_rmse": float(baseline_rmse),
            "baseline_r2": float(baseline_r2),
            "melhoria_mae_percent": float(melhoria_mae),
            "melhoria_rmse_percent": float(melhoria_rmse),
        },
        "amostras_temporais_validas": int(len(dataset)),
    }

    joblib.dump(pacote_modelo, MODEL_PATH)
    joblib.dump(pacote_modelo, MODEL_PATH_COMPAT)

    resumo = pd.DataFrame({
        "informacao": [
            "Sensor",
            "Origem dos dados",
            "Horizonte",
            "Versão de features",
            "Conjunto de features",
            "Modelo escolhido",
            "Amostras Firebase",
            "Amostras temporais válidas",
            "Amostras desenvolvimento",
            "Amostras teste final",
            "MAE teste",
            "RMSE teste",
            "R2 teste",
            "MAE baseline",
            "RMSE baseline",
            "R2 baseline",
            "Melhoria MAE (%)",
            "Melhoria RMSE (%)",
        ],
        "valor": [
            SENSOR_ID,
            "ESP32 + AJ-SR04M + Firebase",
            "60 minutos",
            "v3_tendencia",
            feature_set_name,
            model_name,
            len(df),
            len(dataset),
            len(desenvolvimento),
            len(teste_final),
            mae,
            rmse,
            r2,
            baseline_mae,
            baseline_rmse,
            baseline_r2,
            melhoria_mae,
            melhoria_rmse,
        ],
    })

    resumo.to_csv(SUMMARY_PATH, index=False)

    print("\n" + "=" * 70)
    print("ÚLTIMAS 10 AMOSTRAS DO TESTE")
    print("=" * 70)
    print(
        resultados.tail(10).to_string(index=False)
    )

    print("\n" + "=" * 70)
    print("ARQUIVOS GERADOS")
    print("=" * 70)
    print(f"Modelo principal : {MODEL_PATH}")
    print(f"Modelo compatível: {MODEL_PATH_COMPAT}")
    print(f"Resultados       : {RESULTS_PATH}")
    print(f"Importância      : {IMPORTANCE_PATH}")
    print(f"Resumo           : {SUMMARY_PATH}")
    print(f"Histórico        : {FULL_HISTORY_PATH}")
    print(f"Dataset temporal : {DATASET_PATH}")
    print(f"Comparação       : {SEARCH_PATH}")

    print("\n" + "=" * 70)
    print("TREINAMENTO V3 CONCLUÍDO")
    print("=" * 70)
    print("O modelo final foi treinado com 100% das amostras temporais válidas.")
    print("As novas features de tendência estão registradas no pacote do modelo.")


if __name__ == "__main__":
    treinar()
