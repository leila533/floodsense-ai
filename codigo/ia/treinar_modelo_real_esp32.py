
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
import numpy as np
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit


# ============================================================
# FLOODSENSE AI
# TREINAMENTO DO MODELO REAL DO ESP32
# PREVISÃO DE NÍVEL - 60 MINUTOS
#
# VERSÃO OTIMIZADA:
# - usa TODO o histórico real já coletado
# - não inventa nem interpola leituras
# - procura todas as sequências reais possíveis
# - seleciona automaticamente a melhor configuração
# - valida no bloco temporal mais recente
# - depois treina o modelo final com TODAS as amostras válidas
# - mantém as mesmas 4 features do modelo atual para não quebrar
#   a integração existente do FloodSense
# ============================================================


# ============================================================
# 1. CONFIGURAÇÕES
# ============================================================

# Este arquivo fica em: tcc_3/codigo/ia/
# Portanto parent.parent = tcc_3/codigo/
PASTA_CODIGO = Path(__file__).resolve().parent.parent

FIREBASE_HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
SENSOR_ID = "FS-001"

# Histórico REAL usado no treinamento.
HISTORY_PATH = f"/sensor_history_treinamento/{SENSOR_ID}.json"

# Modelo principal e cópia de compatibilidade.
MODEL_PATH = PASTA_CODIGO / "floodsense_model_60min_esp32.pkl"
MODEL_PATH_COMPAT = PASTA_CODIGO / "floodsense_model_real_esp32_60min.pkl"

RESULTS_PATH = PASTA_CODIGO / "resultados_modelo_real_esp32_60min.csv"
IMPORTANCE_PATH = PASTA_CODIGO / "importancia_variaveis_real_esp32.csv"
SUMMARY_PATH = PASTA_CODIGO / "resumo_modelo_real_esp32.csv"
FULL_HISTORY_PATH = PASTA_CODIGO / "historico_completo_esp32.csv"
DATASET_PATH = PASTA_CODIGO / "dataset_temporal_60min_real.csv"
SEARCH_PATH = PASTA_CODIGO / "comparacao_modelos_otimizacao.csv"


# ============================================================
# 2. CONFIGURAÇÃO TEMPORAL
# ============================================================

# O ESP32 atual grava aproximadamente 1 leitura/minuto.
INTERVALO_ESPERADO_MIN = 1

# Usado somente para diagnóstico.
INTERVALO_MIN = 0.5
INTERVALO_MAX = 2

# Features mantidas iguais ao modelo que já está integrado.
# Isso evita quebrar o código de previsão/dashboard.
FEATURES = [
    "water_level",
    "water_level_lag_1",   # 5 min atrás
    "water_level_lag_3",   # 15 min atrás
    "water_level_lag_6",   # 30 min atrás
]

LAGS_MINUTOS = {
    "water_level_lag_1": 5,
    "water_level_lag_3": 15,
    "water_level_lag_6": 30,
}

TARGET = "target_60min"

TOLERANCIA_LAG_MIN = 2
HORIZONTE_MINUTOS = 60
TOLERANCIA_HORIZONTE_MIN = 2


# ============================================================
# 3. CONFIGURAÇÃO DO TREINAMENTO
# ============================================================

# 80% mais antigos = desenvolvimento
# 20% mais recentes = teste final intocado
PERCENTUAL_TREINO = 0.80

# Para escolher hiperparâmetros, somente os 80% de desenvolvimento
# entram no TimeSeriesSplit. O teste final não participa da escolha.
N_SPLITS_CV = 4

RANDOM_STATE = 42

# Configurações candidatas.
# O script escolhe automaticamente a melhor pela MAE média
# na validação temporal interna.
CONFIGURACOES = [
    {
        "nome": "RF_300_depth12_leaf2",
        "n_estimators": 300,
        "max_depth": 12,
        "min_samples_leaf": 2,
        "max_features": 1.0,
        "bootstrap": True,
    },
    {
        "nome": "RF_500_depth12_leaf1",
        "n_estimators": 500,
        "max_depth": 12,
        "min_samples_leaf": 1,
        "max_features": 1.0,
        "bootstrap": True,
    },
    {
        "nome": "RF_500_depth16_leaf1",
        "n_estimators": 500,
        "max_depth": 16,
        "min_samples_leaf": 1,
        "max_features": 1.0,
        "bootstrap": True,
    },
    {
        "nome": "RF_700_depthNone_leaf1",
        "n_estimators": 700,
        "max_depth": None,
        "min_samples_leaf": 1,
        "max_features": 1.0,
        "bootstrap": True,
    },
    {
        "nome": "RF_700_depth10_leaf2",
        "n_estimators": 700,
        "max_depth": 10,
        "min_samples_leaf": 2,
        "max_features": 1.0,
        "bootstrap": True,
    },
]


# ============================================================
# 4. FUNÇÕES AUXILIARES
# ============================================================

def imprimir_titulo(texto):
    print()
    print("=" * 68)
    print(texto)
    print("=" * 68)


def buscar_historico():
    """Baixa todas as leituras reais do Firebase."""
    url = f"{FIREBASE_HOST}{HISTORY_PATH}"

    imprimir_titulo("BUSCANDO HISTÓRICO REAL DO FIREBASE")

    print(f"[IA REAL] Sensor: {SENSOR_ID}")
    print(f"[IA REAL] URL: {url}")

    resposta = requests.get(url, timeout=30)

    print(f"[IA REAL] HTTP: {resposta.status_code}")

    resposta.raise_for_status()

    dados = resposta.json() or {}

    registros = []

    for chave, valor in dados.items():
        if not isinstance(valor, dict):
            continue

        nivel = valor.get("level")
        timestamp = valor.get("timestamp", chave)

        if nivel is None or timestamp is None:
            continue

        try:
            registros.append(
                {
                    "timestamp": int(timestamp),
                    "water_level": float(nivel),
                }
            )
        except (ValueError, TypeError):
            continue

    if not registros:
        raise RuntimeError(
            "Nenhuma leitura válida foi encontrada no Firebase."
        )

    df = pd.DataFrame(registros)

    df = (
        df.dropna(subset=["timestamp", "water_level"])
        .drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # Remove valores fisicamente impossíveis apenas se existirem.
    # Não altera leituras normais do sensor.
    df = df[
        np.isfinite(df["water_level"])
        & (df["water_level"] >= 0)
    ].copy()

    df = df.reset_index(drop=True)

    if len(df) < 50:
        raise RuntimeError(
            f"Histórico insuficiente: {len(df)} registros."
        )

    return df


def verificar_intervalos(df):
    """Diagnóstico da frequência; não filtra o dataset."""
    if len(df) < 2:
        return

    diferencas = (
        df["timestamp"].diff().dropna() / 60.0
    )

    imprimir_titulo("DIAGNÓSTICO DOS INTERVALOS")

    print(f"Intervalo médio : {diferencas.mean():.2f} min")
    print(f"Intervalo mínimo: {diferencas.min():.2f} min")
    print(f"Intervalo máximo: {diferencas.max():.2f} min")

    dentro = (
        (diferencas >= INTERVALO_MIN)
        & (diferencas <= INTERVALO_MAX)
    )

    print(
        f"Intervalos dentro de {INTERVALO_MIN}-{INTERVALO_MAX} min: "
        f"{dentro.mean() * 100:.1f}%"
    )

    print()
    print("Últimos 30 intervalos:")
    recentes = diferencas.tail(30)

    print(
        f"mediana={recentes.median():.2f} min | "
        f"mínimo={recentes.min():.2f} min | "
        f"máximo={recentes.max():.2f} min"
    )

    print()
    print(
        "ATENÇÃO: os intervalos servem para diagnóstico. "
        "Uma amostra só entra no dataset se possuir todas as "
        "leituras reais necessárias."
    )


def buscar_leitura_proxima(
    timestamps,
    timestamp_alvo,
    tolerancia_segundos,
    indice_atual,
    direcao,
):
    """
    Localiza uma leitura REAL próxima do alvo.

    Não interpola.
    Não inventa.
    Não usa o próprio registro.
    """
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

        distancia = abs(
            int(timestamps[j]) - int(timestamp_alvo)
        )

        if (
            melhor_distancia is None
            or distancia < melhor_distancia
        ):
            melhor_distancia = distancia
            melhor_indice = j

    return melhor_indice


def criar_dataset(df):
    """
    Cria todas as amostras reais possíveis para previsão de 60 min.

    Para cada instante t:
      t - 5  min  -> lag_1
      t - 15 min  -> lag_3
      t - 30 min  -> lag_6
      t + 60 min  -> target

    Tudo é obtido de leituras REAIS.
    """
    imprimir_titulo("CRIANDO DATASET TEMPORAL REAL")

    dados = (
        df.copy()
        .sort_values("timestamp")
        .drop_duplicates("timestamp")
        .reset_index(drop=True)
    )

    timestamps = dados["timestamp"].to_numpy(dtype=np.int64)
    niveis = dados["water_level"].to_numpy(dtype=float)

    tol_lag = int(TOLERANCIA_LAG_MIN * 60)
    tol_futuro = int(TOLERANCIA_HORIZONTE_MIN * 60)

    linhas = []

    descartes_lag = 0
    descartes_futuro = 0

    for i in range(len(dados)):
        timestamp_atual = int(timestamps[i])

        valores_lag = {}
        lags_completos = True

        for nome_feature, minutos in LAGS_MINUTOS.items():
            alvo = timestamp_atual - minutos * 60

            indice = buscar_leitura_proxima(
                timestamps,
                alvo,
                tol_lag,
                i,
                "passado",
            )

            if indice is None:
                lags_completos = False
                break

            valores_lag[nome_feature] = float(niveis[indice])

        if not lags_completos:
            descartes_lag += 1
            continue

        alvo_futuro = timestamp_atual + HORIZONTE_MINUTOS * 60

        indice_futuro = buscar_leitura_proxima(
            timestamps,
            alvo_futuro,
            tol_futuro,
            i,
            "futuro",
        )

        if indice_futuro is None:
            descartes_futuro += 1
            continue

        timestamp_futuro = int(timestamps[indice_futuro])

        diferenca_futura = (
            timestamp_futuro - timestamp_atual
        ) / 60.0

        if not (
            HORIZONTE_MINUTOS - TOLERANCIA_HORIZONTE_MIN
            <= diferenca_futura
            <= HORIZONTE_MINUTOS + TOLERANCIA_HORIZONTE_MIN
        ):
            descartes_futuro += 1
            continue

        linhas.append(
            {
                "timestamp": timestamp_atual,
                "water_level": float(niveis[i]),
                "water_level_lag_1": valores_lag["water_level_lag_1"],
                "water_level_lag_3": valores_lag["water_level_lag_3"],
                "water_level_lag_6": valores_lag["water_level_lag_6"],
                "target_60min": float(niveis[indice_futuro]),
                "intervalo_futuro_min": float(diferenca_futura),
            }
        )

    dataset = pd.DataFrame(linhas)

    print(
        f"[IA REAL] Registros originais: {len(dados)}"
    )
    print(
        f"[IA REAL] Descartados por falta de lag: {descartes_lag}"
    )
    print(
        f"[IA REAL] Descartados por falta de futuro +60 min: "
        f"{descartes_futuro}"
    )
    print(
        f"[IA REAL] AMOSTRAS TEMPORAIS VÁLIDAS: {len(dataset)}"
    )

    if dataset.empty:
        raise RuntimeError(
            "Nenhuma sequência temporal válida foi encontrada."
        )

    dataset = (
        dataset.sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"])
        .reset_index(drop=True)
    )

    return dataset


def mostrar_distribuicao(dataset, titulo="DISTRIBUIÇÃO DOS DADOS"):
    imprimir_titulo(titulo)

    bins = [-np.inf, 20, 40, 60, 80, 100, 120, np.inf]
    nomes = [
        "<20",
        "20-40",
        "40-60",
        "60-80",
        "80-100",
        "100-120",
        ">120",
    ]

    atual = pd.cut(
        dataset["water_level"],
        bins=bins,
        labels=nomes,
        right=False,
    )

    futuro = pd.cut(
        dataset["target_60min"],
        bins=bins,
        labels=nomes,
        right=False,
    )

    print("NÍVEL ATUAL:")
    print(atual.value_counts(sort=False).to_string())

    print()
    print("NÍVEL REAL +60 MIN:")
    print(futuro.value_counts(sort=False).to_string())

    print()
    print(
        f"Atual:  min={dataset['water_level'].min():.1f} | "
        f"máx={dataset['water_level'].max():.1f} | "
        f"média={dataset['water_level'].mean():.1f}"
    )

    print(
        f"+60min: min={dataset['target_60min'].min():.1f} | "
        f"máx={dataset['target_60min'].max():.1f} | "
        f"média={dataset['target_60min'].mean():.1f}"
    )


def criar_pesos_balanceados(y):
    """
    Cria pesos suaves para evitar que uma faixa muito dominante
    mande sozinha no treinamento.

    Os pesos são usados somente durante a seleção de modelos.
    """
    serie = pd.Series(y)

    try:
        grupos = pd.qcut(
            serie.rank(method="first"),
            q=min(5, len(serie)),
            labels=False,
            duplicates="drop",
        )
    except Exception:
        return np.ones(len(serie), dtype=float)

    frequencias = pd.Series(grupos).value_counts()
    pesos = pd.Series(grupos).map(
        lambda grupo: 1.0 / frequencias.get(grupo, 1)
    )

    pesos = pesos / pesos.mean()
    pesos = pesos.clip(lower=0.5, upper=2.5)

    return pesos.to_numpy(dtype=float)


def avaliar_configuracoes(X_dev, y_dev):
    """
    Seleciona hiperparâmetros usando somente o bloco de desenvolvimento.
    O teste final fica intocado.
    """
    imprimir_titulo("OTIMIZAÇÃO TEMPORAL DO MODELO")

    if len(X_dev) < 40:
        raise RuntimeError(
            "Poucos dados para otimização temporal."
        )

    n_splits = min(N_SPLITS_CV, max(2, len(X_dev) // 30))

    tscv = TimeSeriesSplit(n_splits=n_splits)

    resultados = []

    for config in CONFIGURACOES:
        print()
        print(f"Testando: {config['nome']}")

        erros_mae = []
        erros_rmse = []
        scores_r2 = []

        for fold, (train_idx, val_idx) in enumerate(
            tscv.split(X_dev),
            start=1,
        ):
            X_tr = X_dev.iloc[train_idx]
            X_val = X_dev.iloc[val_idx]

            y_tr = y_dev.iloc[train_idx]
            y_val = y_dev.iloc[val_idx]

            modelo = RandomForestRegressor(
                n_estimators=config["n_estimators"],
                max_depth=config["max_depth"],
                min_samples_leaf=config["min_samples_leaf"],
                max_features=config["max_features"],
                bootstrap=config["bootstrap"],
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )

            # Treinamento normal.
            modelo.fit(X_tr, y_tr)

            previsoes = modelo.predict(X_val)

            mae = mean_absolute_error(y_val, previsoes)
            rmse = np.sqrt(
                mean_squared_error(y_val, previsoes)
            )

            if len(y_val) >= 2:
                r2 = r2_score(y_val, previsoes)
            else:
                r2 = np.nan

            erros_mae.append(mae)
            erros_rmse.append(rmse)
            scores_r2.append(r2)

            print(
                f"  Fold {fold}: "
                f"MAE={mae:.3f} | "
                f"RMSE={rmse:.3f} | "
                f"R²={r2:.3f}"
            )

        resultado = {
            "configuracao": config["nome"],
            "mae_cv": float(np.mean(erros_mae)),
            "rmse_cv": float(np.mean(erros_rmse)),
            "r2_cv": float(np.nanmean(scores_r2)),
            **{
                k: v
                for k, v in config.items()
                if k != "nome"
            },
        }

        resultados.append(resultado)

        print(
            f"  MÉDIA: MAE={resultado['mae_cv']:.3f} | "
            f"RMSE={resultado['rmse_cv']:.3f} | "
            f"R²={resultado['r2_cv']:.3f}"
        )

    tabela = (
        pd.DataFrame(resultados)
        .sort_values(
            ["mae_cv", "rmse_cv"],
            ascending=[True, True],
        )
        .reset_index(drop=True)
    )

    tabela.to_csv(
        SEARCH_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    melhor_nome = tabela.iloc[0]["configuracao"]
    melhor = next(
        c for c in CONFIGURACOES
        if c["nome"] == melhor_nome
    )

    imprimir_titulo("MELHOR CONFIGURAÇÃO ENCONTRADA")

    print(f"Configuração: {melhor['nome']}")
    print(f"MAE CV médio : {tabela.iloc[0]['mae_cv']:.4f} cm")
    print(f"RMSE CV médio: {tabela.iloc[0]['rmse_cv']:.4f} cm")
    print(f"R² CV médio  : {tabela.iloc[0]['r2_cv']:.4f}")

    return melhor, tabela


def treinar_modelo(config, X, y):
    """Treina o modelo final usando TODAS as amostras válidas."""
    modelo = RandomForestRegressor(
        n_estimators=config["n_estimators"],
        max_depth=config["max_depth"],
        min_samples_leaf=config["min_samples_leaf"],
        max_features=config["max_features"],
        bootstrap=config["bootstrap"],
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    modelo.fit(X, y)

    return modelo


def salvar_modelo(modelo, config, mae_teste, rmse_teste, r2_teste, total):
    """Salva modelo compatível com o restante do projeto."""
    pacote = {
        "modelo": modelo,
        "features": FEATURES,
        "target": TARGET,
        "horizonte_minutos": HORIZONTE_MINUTOS,
        "timestep_minutos": INTERVALO_ESPERADO_MIN,
        "sensor_id": SENSOR_ID,
        "unidade": "cm",
        "origem_dados": "ESP32 + AJ-SR04M + Firebase",
        "lags": [1, 3, 6],
        "configuracao_modelo": config,
        "amostras_validas": int(total),
        "mae_teste_temporal": float(mae_teste),
        "rmse_teste_temporal": float(rmse_teste),
        "r2_teste_temporal": float(r2_teste),
        "treinado_com_todo_dataset_valido": True,
        "data_treinamento": datetime.now().isoformat(),
    }

    joblib.dump(pacote, MODEL_PATH)
    joblib.dump(pacote, MODEL_PATH_COMPAT)


# ============================================================
# 5. TREINAMENTO PRINCIPAL
# ============================================================

def treinar():
    imprimir_titulo(
        "FLOODSENSE AI - TREINAMENTO OTIMIZADO COM TODO O HISTÓRICO"
    )

    print("Fonte: ESP32 + AJ-SR04M + Firebase")
    print("Sensor:", SENSOR_ID)
    print("Horizonte:", HORIZONTE_MINUTOS, "minutos")
    print("Objetivo: aproveitar ao máximo os dados JÁ coletados.")
    print()
    print(
        "Nenhum dado será inventado, interpolado ou apagado."
    )

    # --------------------------------------------------------
    # 1. Buscar histórico
    # --------------------------------------------------------
    df = buscar_historico()

    df.to_csv(
        FULL_HISTORY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"[IA REAL] Total de registros: {len(df)}")

    verificar_intervalos(df)

    # --------------------------------------------------------
    # 2. Dataset temporal
    # --------------------------------------------------------
    dataset = criar_dataset(df)

    dataset.to_csv(
        DATASET_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    mostrar_distribuicao(
        dataset,
        "DISTRIBUIÇÃO DAS AMOSTRAS TEMPORAIS VÁLIDAS",
    )

    # --------------------------------------------------------
    # 3. Matrizes
    # --------------------------------------------------------
    X = dataset[FEATURES].astype(float)
    y = dataset[TARGET].astype(float)

    if len(dataset) < 30:
        raise RuntimeError(
            f"Apenas {len(dataset)} amostras temporais válidas. "
            "São necessárias pelo menos 30."
        )

    # --------------------------------------------------------
    # 4. Separação temporal
    # --------------------------------------------------------
    ponto_corte = int(
        len(dataset) * PERCENTUAL_TREINO
    )

    X_dev = X.iloc[:ponto_corte].copy()
    y_dev = y.iloc[:ponto_corte].copy()

    X_test = X.iloc[ponto_corte:].copy()
    y_test = y.iloc[ponto_corte:].copy()

    if len(X_test) < 10:
        raise RuntimeError(
            "O teste temporal ficou pequeno demais."
        )

    imprimir_titulo("DIVISÃO TEMPORAL HONESTA")

    print(f"Desenvolvimento: {len(X_dev)} amostras")
    print(f"Teste final     : {len(X_test)} amostras")
    print()
    print(
        "O teste final NÃO participa da escolha do modelo."
    )

    # --------------------------------------------------------
    # 5. Otimização somente no desenvolvimento
    # --------------------------------------------------------
    melhor_config, tabela = avaliar_configuracoes(
        X_dev,
        y_dev,
    )

    # --------------------------------------------------------
    # 6. Avaliação final no bloco recente
    # --------------------------------------------------------
    imprimir_titulo("VALIDAÇÃO FINAL NO BLOCO MAIS RECENTE")

    modelo_avaliacao = RandomForestRegressor(
        n_estimators=melhor_config["n_estimators"],
        max_depth=melhor_config["max_depth"],
        min_samples_leaf=melhor_config["min_samples_leaf"],
        max_features=melhor_config["max_features"],
        bootstrap=melhor_config["bootstrap"],
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    modelo_avaliacao.fit(X_dev, y_dev)

    previsoes = modelo_avaliacao.predict(X_test)

    mae = mean_absolute_error(y_test, previsoes)
    rmse = np.sqrt(
        mean_squared_error(y_test, previsoes)
    )
    r2 = r2_score(y_test, previsoes)

    baseline = X_test["water_level"].to_numpy()

    baseline_mae = mean_absolute_error(
        y_test,
        baseline,
    )

    baseline_rmse = np.sqrt(
        mean_squared_error(
            y_test,
            baseline,
        )
    )

    baseline_r2 = r2_score(
        y_test,
        baseline,
    )

    melhoria_mae = (
        (baseline_mae - mae)
        / baseline_mae
        * 100
        if baseline_mae != 0
        else 0
    )

    melhoria_rmse = (
        (baseline_rmse - rmse)
        / baseline_rmse
        * 100
        if baseline_rmse != 0
        else 0
    )

    print(f"Configuração escolhida: {melhor_config['nome']}")
    print()
    print("RANDOM FOREST - TESTE FINAL")
    print(f"MAE : {mae:.4f} cm")
    print(f"RMSE: {rmse:.4f} cm")
    print(f"R²  : {r2:.6f}")

    print()
    print("BASELINE - NÍVEL ATUAL")
    print(f"MAE : {baseline_mae:.4f} cm")
    print(f"RMSE: {baseline_rmse:.4f} cm")
    print(f"R²  : {baseline_r2:.6f}")

    print()
    print(f"Melhoria MAE : {melhoria_mae:.2f}%")
    print(f"Melhoria RMSE: {melhoria_rmse:.2f}%")

    # --------------------------------------------------------
    # 7. Resultado detalhado do teste
    # --------------------------------------------------------
    resultados = pd.DataFrame(
        {
            "timestamp": dataset.iloc[
                ponto_corte:
            ]["timestamp"].values,

            "nivel_atual_cm": X_test[
                "water_level"
            ].values,

            "nivel_real_60min_cm": y_test.values,

            "nivel_previsto_60min_cm": previsoes,

            "erro_absoluto_cm": np.abs(
                y_test.values - previsoes
            ),

            "erro_cm": (
                y_test.values - previsoes
            ),
        }
    )

    resultados.to_csv(
        RESULTS_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 8. Importância
    # --------------------------------------------------------
    importancias = pd.DataFrame(
        {
            "feature": FEATURES,
            "importance": modelo_avaliacao.feature_importances_,
        }
    ).sort_values(
        "importance",
        ascending=False,
    ).reset_index(drop=True)

    importancias.to_csv(
        IMPORTANCE_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    imprimir_titulo("IMPORTÂNCIA DAS VARIÁVEIS")

    print(importancias.to_string(index=False))

    # --------------------------------------------------------
    # 9. TREINAMENTO FINAL COM 100% DAS AMOSTRAS VÁLIDAS
    # --------------------------------------------------------
    imprimir_titulo(
        "TREINAMENTO FINAL - 100% DOS DADOS TEMPORAIS VÁLIDOS"
    )

    print(
        f"Treinando com {len(X)} amostras válidas..."
    )

    modelo_final = treinar_modelo(
        melhor_config,
        X,
        y,
    )

    print(
        "[IA REAL] Modelo final treinado com TODAS "
        "as amostras temporais válidas."
    )

    # --------------------------------------------------------
    # 10. Salvar modelo final
    # --------------------------------------------------------
    salvar_modelo(
        modelo_final,
        melhor_config,
        mae,
        rmse,
        r2,
        len(dataset),
    )

    # --------------------------------------------------------
    # 11. Resumo
    # --------------------------------------------------------
    resumo = pd.DataFrame(
        {
            "informacao": [
                "Sensor",
                "Origem dos dados",
                "Unidade",
                "Algoritmo",
                "Horizonte",
                "Registros totais Firebase",
                "Amostras temporais válidas",
                "Amostras desenvolvimento",
                "Amostras teste",
                "Configuração escolhida",
                "MAE teste temporal",
                "RMSE teste temporal",
                "R2 teste temporal",
                "MAE baseline",
                "RMSE baseline",
                "R2 baseline",
                "Melhoria MAE percentual",
                "Melhoria RMSE percentual",
                "Modelo final treinado com todo dataset",
            ],
            "valor": [
                SENSOR_ID,
                "ESP32 + AJ-SR04M + Firebase",
                "cm",
                "Random Forest Regressor otimizado",
                "60 minutos",
                len(df),
                len(dataset),
                len(X_dev),
                len(X_test),
                melhor_config["nome"],
                float(mae),
                float(rmse),
                float(r2),
                float(baseline_mae),
                float(baseline_rmse),
                float(baseline_r2),
                float(melhoria_mae),
                float(melhoria_rmse),
                True,
            ],
        }
    )

    resumo.to_csv(
        SUMMARY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    # --------------------------------------------------------
    # 12. Mostrar exemplos
    # --------------------------------------------------------
    imprimir_titulo("ÚLTIMAS 10 AMOSTRAS DO TESTE")

    print(
        resultados.tail(10)[
            [
                "nivel_atual_cm",
                "nivel_real_60min_cm",
                "nivel_previsto_60min_cm",
                "erro_absoluto_cm",
            ]
        ].to_string(index=False)
    )

    # --------------------------------------------------------
    # 13. Arquivos
    # --------------------------------------------------------
    imprimir_titulo("ARQUIVOS GERADOS")

    print("Modelo principal:")
    print(MODEL_PATH)

    print()
    print("Modelo compatível:")
    print(MODEL_PATH_COMPAT)

    print()
    print("Resultados:")
    print(RESULTS_PATH)

    print()
    print("Importância:")
    print(IMPORTANCE_PATH)

    print()
    print("Resumo:")
    print(SUMMARY_PATH)

    print()
    print("Histórico completo:")
    print(FULL_HISTORY_PATH)

    print()
    print("Dataset temporal:")
    print(DATASET_PATH)

    print()
    print("Comparação da otimização:")
    print(SEARCH_PATH)

    # --------------------------------------------------------
    # 14. Final
    # --------------------------------------------------------
    imprimir_titulo("TREINAMENTO CONCLUÍDO")

    print(
        "FloodSense AI: modelo real do ESP32 processado."
    )
    print(
        "O modelo final foi treinado com 100% das "
        "amostras temporais válidas encontradas."
    )
    print(
        "A validação exibida acima continua sendo feita "
        "somente no bloco temporal mais recente."
    )
    print()
    


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    treinar()
