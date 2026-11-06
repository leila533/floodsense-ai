from pathlib import Path

import requests
import pandas as pd
import numpy as np
import joblib

from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit


# ============================================================
# FLOODSENSE AI - V4 PROGRESSIVO
# TREINAMENTO REAL DO ESP32 - PREVISÃO DE 60 MINUTOS
#
# Evolução do V3: em vez de UM modelo que exige 30 min de histórico,
# treina QUATRO modelos independentes, cada um com exatamente as
# features que existem quando o histórico ainda é curto:
#
#   STARTUP : water_level
#   LAG_5   : water_level, water_level_lag_1
#   LAG_15  : water_level, water_level_lag_1, water_level_lag_3
#   FULL    : water_level, water_level_lag_1, water_level_lag_3,
#             water_level_lag_6
#
# Regras mantidas do V3:
#   - somente dados reais do ESP32 + AJ-SR04M + Firebase (FS-001)
#   - nada de interpolação ou preenchimento de valores
#   - lags buscados por TIMESTAMP, com tolerância de ±2 min
#   - divisão temporal 80% desenvolvimento / 20% teste final
#   - TimeSeriesSplit somente no desenvolvimento
#   - escolha do algoritmo SOMENTE com o desenvolvimento
#   - avaliação final no bloco mais recente (teste final)
#   - treino final com 100% das amostras válidas de cada modelo
#
# Observação: no dataset de trabalho, um lag que não existe fica NaN
# apenas como marcador de "indisponível". Nenhum modelo recebe NaN:
# cada modelo só usa as linhas em que TODAS as suas features existem.
# ============================================================


# ============================================================
# 1. CONFIGURAÇÕES
# ============================================================

PASTA_CODIGO = Path(__file__).resolve().parent.parent

FIREBASE_HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
SENSOR_ID = "FS-001"

HISTORY_PATH = f"/sensor_history_treinamento/{SENSOR_ID}.json"

MODEL_VERSION = "v4_progressivo"

MODEL_PATH = PASTA_CODIGO / "floodsense_modelos_progressivos_60min_esp32.pkl"

COMPARISON_PATH = PASTA_CODIGO / "comparacao_modelos_progressivos.csv"
RESULTS_PATH = PASTA_CODIGO / "resultados_modelos_progressivos.csv"
SUMMARY_PATH = PASTA_CODIGO / "resumo_modelos_progressivos.csv"
IMPORTANCE_PATH = PASTA_CODIGO / "importancia_variaveis_progressivos.csv"
FULL_HISTORY_PATH = PASTA_CODIGO / "historico_completo_esp32.csv"
DATASET_PATH = PASTA_CODIGO / "dataset_temporal_progressivo_60min_real.csv"

TOLERANCIA_LAG_MIN = 2
HORIZONTE_MINUTOS = 60
TOLERANCIA_HORIZONTE_MIN = 2

# Mínimos para treinar/avaliar um modelo progressivo.
MIN_AMOSTRAS_MODELO = 40
MIN_AMOSTRAS_DESENVOLVIMENTO = 20

LAGS_MINUTOS = {
    "water_level_lag_1": 5,
    "water_level_lag_3": 15,
    "water_level_lag_6": 30,
}

TARGET = "target_60min"

# Ordem do mais simples para o mais completo.
# As features de cada modelo são EXATAMENTE as listadas aqui.
MODELOS_PROGRESSIVOS = {
    "STARTUP": {
        "lags": [],
    },
    "LAG_5": {
        "lags": ["water_level_lag_1"],
    },
    "LAG_15": {
        "lags": ["water_level_lag_1", "water_level_lag_3"],
    },
    "FULL": {
        "lags": ["water_level_lag_1", "water_level_lag_3", "water_level_lag_6"],
    },
}

for _cfg in MODELOS_PROGRESSIVOS.values():
    _cfg["features"] = ["water_level"] + _cfg["lags"]

# O serviço escolhe sempre o mais completo que puder ser alimentado.
ORDEM_PRIORIDADE = ["FULL", "LAG_15", "LAG_5", "STARTUP"]


# ============================================================
# 2. HISTÓRICO
# ============================================================

def buscar_historico():
    url = f"{FIREBASE_HOST}{HISTORY_PATH}"

    print("\n" + "=" * 70)
    print("FLOODSENSE AI V4 - BUSCANDO HISTÓRICO REAL")
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
            nivel = float(nivel)
            registros.append({
                "timestamp": int(timestamp),
                "water_level": nivel,
            })
        except (ValueError, TypeError):
            continue

    if not registros:
        raise RuntimeError("Nenhum registro válido encontrado no Firebase.")

    df = pd.DataFrame(registros)
    df = df[np.isfinite(df["water_level"])]
    df = (
        df.drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# 3. LOCALIZAÇÃO DE LEITURA REAL (idêntica ao V3 / ao serviço)
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
# 4. DATASET TEMPORAL
# ============================================================

def criar_dataset(df):
    """
    Uma linha por leitura que possui alvo real em +60 min.
    Lags que não existem dentro da tolerância ficam NaN (marcador de
    indisponível). Eles NUNCA são preenchidos.
    """
    print("\n" + "=" * 70)
    print("CRIANDO DATASET TEMPORAL V4")
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
    sem_futuro = 0
    sem_lag = {nome: 0 for nome in LAGS_MINUTOS}

    for i in range(len(dados)):
        atual = int(timestamps[i])

        idx_futuro = buscar_leitura_proxima(
            timestamps,
            atual + HORIZONTE_MINUTOS * 60,
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
            sem_futuro += 1
            continue

        linha = {
            "timestamp": atual,
            "water_level": float(niveis[i]),
        }

        for nome, minutos in LAGS_MINUTOS.items():
            idx = buscar_leitura_proxima(
                timestamps,
                atual - minutos * 60,
                tol_lag,
                i,
                "passado",
            )

            if idx is None:
                linha[nome] = np.nan
                sem_lag[nome] += 1
            else:
                linha[nome] = float(niveis[idx])

        linha[TARGET] = float(niveis[idx_futuro])
        linha["intervalo_futuro_min"] = float(diferenca_futura)

        linhas.append(linha)

    dataset = pd.DataFrame(linhas)

    print(f"Registros originais: {len(df)}")
    print(f"Descartados por falta de futuro +60 min: {sem_futuro}")
    print(f"Amostras com alvo real (+60 min): {len(dataset)}")
    for nome, minutos in LAGS_MINUTOS.items():
        print(f"  Sem {nome} ({minutos} min): {sem_lag[nome]}")

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
        f"Nível +60: min={dataset[TARGET].min():.1f} | "
        f"máx={dataset[TARGET].max():.1f} | "
        f"média={dataset[TARGET].mean():.1f}"
    )

    print("\nAmostras válidas por modelo progressivo:")
    for nome, cfg in MODELOS_PROGRESSIVOS.items():
        n = int(dataset.dropna(subset=cfg["features"] + [TARGET]).shape[0])
        print(f"  {nome:<8} {n:>7}  ({', '.join(cfg['features'])})")


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
# 7. MÉTRICAS
# ============================================================

def calcular_metricas(y_real, y_previsto):
    if len(y_real) == 0:
        return np.nan, np.nan, np.nan

    mae = mean_absolute_error(y_real, y_previsto)
    rmse = float(np.sqrt(mean_squared_error(y_real, y_previsto)))
    r2 = r2_score(y_real, y_previsto) if len(y_real) >= 2 else np.nan

    return float(mae), rmse, float(r2)


# ============================================================
# 8. OTIMIZAÇÃO TEMPORAL (por modelo progressivo)
# ============================================================

def otimizar(nome_progressivo, features, desenvolvimento):
    print("\n" + "-" * 70)
    print(f"OTIMIZAÇÃO TEMPORAL - {nome_progressivo} ({', '.join(features)})")
    print("-" * 70)

    tscv = TimeSeriesSplit(n_splits=4)
    X = desenvolvimento[features]
    y = desenvolvimento[TARGET]

    resultados = []

    for nome_algoritmo, modelo_base in criar_modelos().items():
        maes, rmses, r2s = [], [], []

        for train_idx, val_idx in tscv.split(X):
            modelo = modelo_base.__class__(**modelo_base.get_params())

            modelo.fit(X.iloc[train_idx], y.iloc[train_idx])
            pred = modelo.predict(X.iloc[val_idx])

            mae, rmse, r2 = calcular_metricas(y.iloc[val_idx], pred)
            maes.append(mae)
            rmses.append(rmse)
            r2s.append(r2)

        media_mae = float(np.mean(maes))
        media_rmse = float(np.mean(rmses))
        media_r2 = float(np.nanmean(r2s))

        print(
            f"  {nome_algoritmo:<26} "
            f"MAE={media_mae:.3f} | RMSE={media_rmse:.3f} | R²={media_r2:.3f}"
        )

        resultados.append({
            "modelo_progressivo": nome_progressivo,
            "feature_set": nome_progressivo,
            "algoritmo": nome_algoritmo,
            "mae_cv": media_mae,
            "rmse_cv": media_rmse,
            "r2_cv": media_r2,
        })

    busca = (
        pd.DataFrame(resultados)
        .sort_values(["mae_cv", "rmse_cv"], ascending=[True, True])
        .reset_index(drop=True)
    )

    melhor = busca.iloc[0]

    print(
        f"  >> Melhor: {melhor['algoritmo']} "
        f"(MAE CV={melhor['mae_cv']:.4f} cm)"
    )

    return busca, melhor


# ============================================================
# 9. TREINAMENTO DE UM MODELO PROGRESSIVO
# ============================================================

def treinar_progressivo(nome, cfg, dataset, ts_corte, n_firebase):
    features = cfg["features"]

    print("\n" + "=" * 70)
    print(f"MODELO {nome}")
    print("=" * 70)
    print(f"Features: {features}")

    validos = (
        dataset.dropna(subset=features + [TARGET])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # Mesmo instante de corte para os 4 modelos: todos são avaliados
    # no mesmo período recente, o que torna as métricas comparáveis.
    desenvolvimento = validos[validos["timestamp"] < ts_corte].copy()
    teste_final = validos[validos["timestamp"] >= ts_corte].copy()

    resumo = {
        "modelo_progressivo": nome,
        "features": ", ".join(features),
        "lags_utilizados": ", ".join(
            f"{LAGS_MINUTOS[l]}min" for l in cfg["lags"]
        ) or "nenhum",
        "amostras_firebase": int(n_firebase),
        "amostras_disponiveis": int(len(dataset)),
        "amostras_validas": int(len(validos)),
        "amostras_desenvolvimento": int(len(desenvolvimento)),
        "amostras_teste": int(len(teste_final)),
    }

    print(f"Amostras com alvo real: {len(dataset)}")
    print(f"Amostras válidas p/ este modelo: {len(validos)}")
    print(f"Desenvolvimento: {len(desenvolvimento)} | Teste final: {len(teste_final)}")

    if len(validos) < MIN_AMOSTRAS_MODELO or len(desenvolvimento) < MIN_AMOSTRAS_DESENVOLVIMENTO:
        motivo = (
            f"amostras insuficientes (válidas={len(validos)}, "
            f"desenvolvimento={len(desenvolvimento)})"
        )
        print(f"!! {nome} NÃO treinado: {motivo}")
        resumo["status"] = f"nao_treinado: {motivo}"
        return None, resumo, None, None, None

    busca, melhor = otimizar(nome, features, desenvolvimento)

    nome_algoritmo = str(melhor["algoritmo"])
    modelo_base = criar_modelos()[nome_algoritmo]

    # Avaliação final: treina só no desenvolvimento, testa no bloco recente.
    modelo_teste = modelo_base.__class__(**modelo_base.get_params())
    modelo_teste.fit(desenvolvimento[features], desenvolvimento[TARGET])

    if len(teste_final) > 0:
        pred_teste = modelo_teste.predict(teste_final[features])
        baseline = teste_final["water_level"].to_numpy()

        mae, rmse, r2 = calcular_metricas(teste_final[TARGET], pred_teste)
        b_mae, b_rmse, b_r2 = calcular_metricas(teste_final[TARGET], baseline)
    else:
        pred_teste = np.array([])
        mae = rmse = r2 = b_mae = b_rmse = b_r2 = np.nan

    melhoria_mae = (b_mae - mae) / b_mae * 100 if b_mae else np.nan
    melhoria_rmse = (b_rmse - rmse) / b_rmse * 100 if b_rmse else np.nan

    print(f"\nValidação final {nome} - {nome_algoritmo}")
    print(f"  MAE : {mae:.4f} cm   (baseline {b_mae:.4f})")
    print(f"  RMSE: {rmse:.4f} cm   (baseline {b_rmse:.4f})")
    print(f"  R²  : {r2:.6f}   (baseline {b_r2:.6f})")
    print(f"  Melhoria MAE: {melhoria_mae:.2f}% | RMSE: {melhoria_rmse:.2f}%")

    # Treino final com 100% das amostras válidas deste modelo.
    modelo_final = modelo_base.__class__(**modelo_base.get_params())
    modelo_final.fit(validos[features], validos[TARGET])

    importancias = pd.DataFrame({
        "modelo_progressivo": nome,
        "feature": features,
        "importance": modelo_final.feature_importances_
        if hasattr(modelo_final, "feature_importances_")
        else np.nan,
    }).sort_values("importance", ascending=False)

    resultados = teste_final[["timestamp", "water_level", TARGET]].copy()
    resultados["nivel_previsto_60min_cm"] = pred_teste
    resultados["erro_absoluto_cm"] = np.abs(
        resultados[TARGET] - resultados["nivel_previsto_60min_cm"]
    )
    resultados = resultados.rename(columns={
        "water_level": "nivel_atual_cm",
        TARGET: "nivel_real_60min_cm",
    })
    resultados.insert(0, "modelo_progressivo", nome)

    metricas_teste = {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "baseline_mae": b_mae,
        "baseline_rmse": b_rmse,
        "baseline_r2": b_r2,
        "melhoria_mae_percent": melhoria_mae,
        "melhoria_rmse_percent": melhoria_rmse,
    }

    resumo.update({
        "status": "treinado",
        "algoritmo": nome_algoritmo,
        "mae_cv": float(melhor["mae_cv"]),
        "rmse_cv": float(melhor["rmse_cv"]),
        "r2_cv": float(melhor["r2_cv"]),
        "mae_teste": mae,
        "rmse_teste": rmse,
        "r2_teste": r2,
        "mae_baseline": b_mae,
        "rmse_baseline": b_rmse,
        "r2_baseline": b_r2,
        "melhoria_mae_percent": melhoria_mae,
        "melhoria_rmse_percent": melhoria_rmse,
    })

    pacote_modelo = {
        "modelo": modelo_final,
        "nome": nome,
        "features": list(features),
        "lags_necessarios": list(cfg["lags"]),
        "lags_minutos": {l: LAGS_MINUTOS[l] for l in cfg["lags"]},
        "algoritmo": nome_algoritmo,
        "algoritmo_classe": type(modelo_final).__name__,
        "feature_set": nome,
        "feature_version": MODEL_VERSION,
        "versao_modelo": MODEL_VERSION,
        "target": TARGET,
        "horizonte_minutos": HORIZONTE_MINUTOS,
        "sensor_id": SENSOR_ID,
        "unidade": "cm",
        "origem_dados": "ESP32 + AJ-SR04M + Firebase",
        "history_path_treinamento": HISTORY_PATH,
        "tolerancia_lag_min": TOLERANCIA_LAG_MIN,
        "tolerancia_horizonte_min": TOLERANCIA_HORIZONTE_MIN,
        "metricas_cv": {
            "mae": float(melhor["mae_cv"]),
            "rmse": float(melhor["rmse_cv"]),
            "r2": float(melhor["r2_cv"]),
        },
        "metricas_teste": metricas_teste,
        "amostras_disponiveis": int(len(dataset)),
        "amostras_validas": int(len(validos)),
        "amostras_desenvolvimento": int(len(desenvolvimento)),
        "amostras_teste": int(len(teste_final)),
    }

    return pacote_modelo, resumo, busca, resultados, importancias


# ============================================================
# 10. TREINAMENTO COMPLETO
# ============================================================

def treinar():
    print("\n" + "=" * 70)
    print("FLOODSENSE AI V4 - MODELOS PROGRESSIVOS")
    print("MODELO REAL DO ESP32 - PREVISÃO DE 60 MINUTOS")
    print("=" * 70)

    df = buscar_historico()
    df.to_csv(FULL_HISTORY_PATH, index=False)

    dataset = criar_dataset(df)
    diagnostico(df, dataset)
    dataset.to_csv(DATASET_PATH, index=False)

    if len(dataset) < MIN_AMOSTRAS_MODELO:
        raise RuntimeError(
            f"Amostras temporais insuficientes: {len(dataset)}."
        )

    # Corte 80/20 definido sobre todas as amostras com alvo real
    # e aplicado como TIMESTAMP aos quatro modelos.
    corte = int(len(dataset) * 0.80)
    corte = min(corte, len(dataset) - 1)
    ts_corte = int(dataset.iloc[corte]["timestamp"])

    print("\n" + "=" * 70)
    print("DIVISÃO TEMPORAL HONESTA (80% / 20%)")
    print("=" * 70)
    print(f"Timestamp de corte: {ts_corte}")
    print("O teste final NÃO participa da escolha do algoritmo.")

    pacotes = {}
    resumos = []
    comparacoes = []
    resultados_amostras = []
    importancias_todas = []

    for nome, cfg in MODELOS_PROGRESSIVOS.items():
        pacote_modelo, resumo, busca, resultados, importancias = treinar_progressivo(
            nome, cfg, dataset, ts_corte, len(df),
        )

        resumos.append(resumo)

        if pacote_modelo is None:
            continue

        pacotes[nome] = pacote_modelo
        comparacoes.append(busca)
        resultados_amostras.append(resultados)
        importancias_todas.append(importancias)

    if not pacotes:
        raise RuntimeError("Nenhum modelo progressivo pôde ser treinado.")

    if "STARTUP" not in pacotes:
        print(
            "\n!! ATENÇÃO: STARTUP não foi treinado. "
            "Sem ele, o serviço não consegue prever logo após reiniciar o ESP32."
        )

    pacote_final = {
        "tipo": "modelos_progressivos",
        "versao_pacote": MODEL_VERSION,
        "ordem_prioridade": [n for n in ORDEM_PRIORIDADE if n in pacotes],
        "target": TARGET,
        "horizonte_minutos": HORIZONTE_MINUTOS,
        "timestep_minutos": 1,
        "sensor_id": SENSOR_ID,
        "unidade": "cm",
        "origem_dados": "ESP32 + AJ-SR04M + Firebase",
        "history_path_treinamento": HISTORY_PATH,
        "lags_minutos": dict(LAGS_MINUTOS),
        "tolerancia_lag_min": TOLERANCIA_LAG_MIN,
        "tolerancia_horizonte_min": TOLERANCIA_HORIZONTE_MIN,
        "timestamp_corte_teste": ts_corte,
        "modelos": pacotes,
    }

    joblib.dump(pacote_final, MODEL_PATH)

    pd.concat(comparacoes, ignore_index=True).to_csv(COMPARISON_PATH, index=False)

    if resultados_amostras:
        pd.concat(resultados_amostras, ignore_index=True).to_csv(RESULTS_PATH, index=False)

    pd.concat(importancias_todas, ignore_index=True).to_csv(IMPORTANCE_PATH, index=False)

    resumo_df = pd.DataFrame(resumos)
    resumo_df.to_csv(SUMMARY_PATH, index=False)

    print("\n" + "=" * 70)
    print("RESUMO DOS MODELOS PROGRESSIVOS (teste final, bloco mais recente)")
    print("=" * 70)

    colunas = [
        "modelo_progressivo", "status", "algoritmo",
        "amostras_validas", "amostras_teste",
        "mae_teste", "rmse_teste", "r2_teste",
        "mae_baseline", "melhoria_mae_percent",
    ]
    colunas = [c for c in colunas if c in resumo_df.columns]
    print(resumo_df[colunas].to_string(index=False))

    print("\n" + "=" * 70)
    print("ARQUIVOS GERADOS")
    print("=" * 70)
    print(f"Pacote de modelos : {MODEL_PATH}")
    print(f"Comparação        : {COMPARISON_PATH}")
    print(f"Resultados teste  : {RESULTS_PATH}")
    print(f"Resumo            : {SUMMARY_PATH}")
    print(f"Importância       : {IMPORTANCE_PATH}")
    print(f"Histórico         : {FULL_HISTORY_PATH}")
    print(f"Dataset temporal  : {DATASET_PATH}")

    print("\n" + "=" * 70)
    print("TREINAMENTO V4 PROGRESSIVO CONCLUÍDO")
    print("=" * 70)
    print("Cada modelo foi treinado com 100% das suas amostras válidas.")


if __name__ == "__main__":
    treinar()