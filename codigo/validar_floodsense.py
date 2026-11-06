from pathlib import Path

import requests
import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


# ============================================================
# FLOODSENSE AI
# VALIDAÇÃO DO MODELO REAL DO ESP32
# PREVISÃO DE NÍVEL - 60 MINUTOS
# ============================================================


print("=" * 70)
print("FLOODSENSE AI - VALIDAÇÃO DO MODELO REAL DO ESP32")
print("=" * 70)


# ============================================================
# 1. CONFIGURAÇÕES
# ============================================================

# Este arquivo está dentro de:
#
# tcc_3/
#   codigo/
#       validar_floodsense.py
#
# Portanto, usamos a própria pasta do arquivo
# como pasta principal dos modelos e resultados.

PASTA_CODIGO = Path(__file__).resolve().parent


FIREBASE_HOST = (
    "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
)


SENSOR_ID = "FS-001"


HISTORY_PATH = (
    f"/sensor_history_treinamento/{SENSOR_ID}.json"
)


# ============================================================
# 2. MODELO
# ============================================================

MODEL_PATH = (
    PASTA_CODIGO /
    "floodsense_model_60min_esp32.pkl"
)


MODEL_PATH_COMPAT = (
    PASTA_CODIGO /
    "floodsense_model_real_esp32_60min.pkl"
)


# ============================================================
# 3. ARQUIVOS DE SAÍDA
# ============================================================

VALIDATION_PATH = (
    PASTA_CODIGO /
    "validacao_modelo_real_esp32.csv"
)


SUMMARY_PATH = (
    PASTA_CODIGO /
    "resumo_validacao_modelo_real_esp32.csv"
)


# ============================================================
# 4. CONFIGURAÇÃO TEMPORAL
# ============================================================

# O modelo real do ESP32 foi treinado usando:
#
# nível atual
# nível aproximadamente 5 minutos atrás
# nível aproximadamente 15 minutos atrás
# nível aproximadamente 30 minutos atrás
#
# para prever:
#
# nível aproximadamente 60 minutos no futuro.


LAGS_MINUTOS = {
    "water_level_lag_1": 5,
    "water_level_lag_3": 15,
    "water_level_lag_6": 30
}


TOLERANCIA_LAG_MIN = 2


HORIZONTE_MINUTOS = 60


TOLERANCIA_HORIZONTE_MIN = 2


FEATURES_PADRAO = [
    "water_level",
    "water_level_lag_1",
    "water_level_lag_3",
    "water_level_lag_6"
]


TARGET = "target_60min"


# ============================================================
# 5. CARREGAR MODELO
# ============================================================

print()
print("=" * 70)
print("CARREGANDO MODELO")
print("=" * 70)


if MODEL_PATH.exists():

    caminho_modelo = MODEL_PATH

elif MODEL_PATH_COMPAT.exists():

    caminho_modelo = MODEL_PATH_COMPAT

else:

    print()
    print("ERRO: modelo não encontrado.")
    print()
    print("O programa procurou em:")
    print()
    print(MODEL_PATH)
    print()
    print("E também em:")
    print()
    print(MODEL_PATH_COMPAT)
    print()

    raise FileNotFoundError(
        "Nenhum modelo FloodSense foi encontrado."
    )


print()
print("Arquivo encontrado:")
print(caminho_modelo)


pacote_modelo = joblib.load(
    caminho_modelo
)


# ============================================================
# 6. INTERPRETAR O PACOTE DO MODELO
# ============================================================

if isinstance(
    pacote_modelo,
    dict
):

    if "modelo" not in pacote_modelo:

        raise RuntimeError(
            "O pacote do modelo não possui a chave 'modelo'."
        )


    modelo = pacote_modelo[
        "modelo"
    ]


    features_modelo = pacote_modelo.get(
        "features",
        FEATURES_PADRAO
    )


    horizonte_modelo = pacote_modelo.get(
        "horizonte_minutos",
        HORIZONTE_MINUTOS
    )


    sensor_modelo = pacote_modelo.get(
        "sensor_id",
        SENSOR_ID
    )


else:

    # Caso o arquivo seja diretamente
    # um Random Forest, ainda conseguimos
    # trabalhar com ele.

    modelo = pacote_modelo


    features_modelo = FEATURES_PADRAO


    horizonte_modelo = HORIZONTE_MINUTOS


    sensor_modelo = SENSOR_ID


print()
print("Modelo carregado com sucesso!")


print(
    f"Sensor: {sensor_modelo}"
)


print(
    f"Horizonte: {horizonte_modelo} minutos"
)


print(
    f"Features utilizadas: {features_modelo}"
)


# ============================================================
# 7. BUSCAR HISTÓRICO REAL DO FIREBASE
# ============================================================

print()
print("=" * 70)
print("BUSCANDO HISTÓRICO REAL DO FIREBASE")
print("=" * 70)


url = (
    f"{FIREBASE_HOST}"
    f"{HISTORY_PATH}"
)


print()
print(
    f"Sensor: {SENSOR_ID}"
)


print(
    f"URL: {url}"
)


try:

    resposta = requests.get(
        url,
        timeout=30
    )

except requests.RequestException as erro:

    raise RuntimeError(
        f"Erro ao acessar o Firebase: {erro}"
    )


print()
print(
    f"HTTP: {resposta.status_code}"
)


resposta.raise_for_status()


dados = resposta.json()


if not dados:

    raise RuntimeError(
        "O Firebase retornou zero registros."
    )


# ============================================================
# 8. TRANSFORMAR HISTÓRICO EM DATAFRAME
# ============================================================

registros = []


for chave, valor in dados.items():

    if not isinstance(
        valor,
        dict
    ):

        continue


    timestamp = valor.get(
        "timestamp",
        chave
    )


    nivel = valor.get(
        "level"
    )


    if timestamp is None:

        continue


    if nivel is None:

        continue


    try:

        timestamp = int(
            timestamp
        )


        nivel = float(
            nivel
        )


    except (
        ValueError,
        TypeError
    ):

        continue


    registros.append(
        {
            "timestamp": timestamp,
            "water_level": nivel
        }
    )


if not registros:

    raise RuntimeError(
        "Nenhum registro válido foi encontrado "
        "no histórico do Firebase."
    )


df = pd.DataFrame(
    registros
)


# ============================================================
# 9. LIMPAR E ORDENAR HISTÓRICO
# ============================================================

df = (
    df
    .drop_duplicates(
        subset=["timestamp"]
    )
    .sort_values(
        "timestamp"
    )
    .reset_index(
        drop=True
    )
)


print()
print(
    f"Registros encontrados: {len(df)}"
)


print(
    f"Primeiro timestamp: "
    f"{df.iloc[0]['timestamp']}"
)


print(
    f"Último timestamp: "
    f"{df.iloc[-1]['timestamp']}"
)


# ============================================================
# 10. DIAGNÓSTICO DOS INTERVALOS
# ============================================================

print()
print("=" * 70)
print("DIAGNÓSTICO DOS INTERVALOS")
print("=" * 70)


if len(df) >= 2:

    intervalos = (
        df["timestamp"]
        .diff()
        .dropna()
        / 60
    )


    print(
        f"Intervalo médio: "
        f"{intervalos.mean():.2f} min"
    )


    print(
        f"Intervalo mediano: "
        f"{intervalos.median():.2f} min"
    )


    print(
        f"Menor intervalo: "
        f"{intervalos.min():.2f} min"
    )


    print(
        f"Maior intervalo: "
        f"{intervalos.max():.2f} min"
    )


    print()
    print(
        "Últimos 20 intervalos:"
    )


    print(
        intervalos
        .tail(20)
        .round(2)
        .to_string(
            index=False
        )
    )


# ============================================================
# 11. FUNÇÃO PARA ENCONTRAR LEITURA PRÓXIMA
# ============================================================

def buscar_leitura_proxima(
    timestamps,
    timestamp_alvo,
    tolerancia_segundos,
    indice_atual,
    direcao
):

    esquerda = np.searchsorted(
        timestamps,
        timestamp_alvo - tolerancia_segundos,
        side="left"
    )


    direita = np.searchsorted(
        timestamps,
        timestamp_alvo + tolerancia_segundos,
        side="right"
    )


    melhor_indice = None


    melhor_distancia = None


    for j in range(
        esquerda,
        direita
    ):

        if j == indice_atual:

            continue


        if (
            direcao == "passado"
            and j >= indice_atual
        ):

            continue


        if (
            direcao == "futuro"
            and j <= indice_atual
        ):

            continue


        distancia = abs(
            timestamps[j]
            - timestamp_alvo
        )


        if (
            melhor_distancia is None
            or distancia < melhor_distancia
        ):

            melhor_distancia = distancia


            melhor_indice = j


    return melhor_indice


# ============================================================
# 12. CRIAR DATASET TEMPORAL
# ============================================================

print()
print("=" * 70)
print("CRIANDO DATASET TEMPORAL DE VALIDAÇÃO")
print("=" * 70)


timestamps = (
    df["timestamp"]
    .to_numpy()
)


niveis = (
    df["water_level"]
    .to_numpy()
)


tolerancia_lag_seg = (
    TOLERANCIA_LAG_MIN * 60
)


tolerancia_horizonte_seg = (
    TOLERANCIA_HORIZONTE_MIN * 60
)


linhas = []


descartes_sem_lag = 0


descartes_sem_futuro = 0


for i in range(
    len(df)
):

    timestamp_atual = int(
        timestamps[i]
    )


    # ========================================================
    # LAGS
    # ========================================================

    valores_lag = {}


    lags_completos = True


    for nome_feature, minutos in (
        LAGS_MINUTOS.items()
    ):

        timestamp_alvo = (
            timestamp_atual
            - minutos * 60
        )


        indice_lag = buscar_leitura_proxima(
            timestamps,
            timestamp_alvo,
            tolerancia_lag_seg,
            i,
            "passado"
        )


        if indice_lag is None:

            lags_completos = False

            break


        valores_lag[
            nome_feature
        ] = niveis[
            indice_lag
        ]


    if not lags_completos:

        descartes_sem_lag += 1

        continue


    # ========================================================
    # LEITURA REAL +60 MINUTOS
    # ========================================================

    timestamp_alvo_futuro = (
        timestamp_atual
        + HORIZONTE_MINUTOS * 60
    )


    indice_futuro = buscar_leitura_proxima(
        timestamps,
        timestamp_alvo_futuro,
        tolerancia_horizonte_seg,
        i,
        "futuro"
    )


    if indice_futuro is None:

        descartes_sem_futuro += 1

        continue


    timestamp_futuro = int(
        timestamps[
            indice_futuro
        ]
    )


    diferenca_futura_min = (
        timestamp_futuro
        - timestamp_atual
    ) / 60.0


    if not (
        58
        <= diferenca_futura_min
        <= 62
    ):

        continue


    # ========================================================
    # ADICIONAR AMOSTRA
    # ========================================================

    linhas.append(
        {
            "timestamp":
                timestamp_atual,

            "water_level":
                niveis[i],

            "water_level_lag_1":
                valores_lag[
                    "water_level_lag_1"
                ],

            "water_level_lag_3":
                valores_lag[
                    "water_level_lag_3"
                ],

            "water_level_lag_6":
                valores_lag[
                    "water_level_lag_6"
                ],

            "target_60min":
                niveis[
                    indice_futuro
                ],

            "intervalo_futuro_min":
                diferenca_futura_min
        }
    )


dataset = pd.DataFrame(
    linhas
)


# ============================================================
# 13. VERIFICAR DATASET
# ============================================================

if dataset.empty:

    raise RuntimeError(
        "\nNenhuma sequência temporal válida "
        "foi encontrada para validação.\n\n"
        "É necessário ter leituras contínuas "
        "com lags de 5, 15 e 30 minutos "
        "e uma leitura real aproximadamente "
        "60 minutos depois."
    )


dataset = (
    dataset
    .sort_values(
        "timestamp"
    )
    .reset_index(
        drop=True
    )
)


print()
print(
    f"Registros originais: "
    f"{len(df)}"
)


print(
    f"Descartados por falta de lag: "
    f"{descartes_sem_lag}"
)


print(
    f"Descartados por falta de futuro +60min: "
    f"{descartes_sem_futuro}"
)


print(
    f"Amostras temporais válidas: "
    f"{len(dataset)}"
)


print(
    f"Horizonte médio: "
    f"{dataset['intervalo_futuro_min'].mean():.2f} min"
)


print(
    f"Horizonte mínimo: "
    f"{dataset['intervalo_futuro_min'].min():.2f} min"
)


print(
    f"Horizonte máximo: "
    f"{dataset['intervalo_futuro_min'].max():.2f} min"
)


# ============================================================
# 14. DIVISÃO TEMPORAL
# ============================================================

print()
print("=" * 70)
print("DIVISÃO TEMPORAL")
print("=" * 70)


ponto_corte = int(
    len(dataset) * 0.80
)


if ponto_corte <= 0:

    raise RuntimeError(
        "Não foi possível criar o conjunto de validação."
    )


X = dataset[
    features_modelo
]


y = dataset[
    TARGET
]


X_teste = X.iloc[
    ponto_corte:
].copy()


y_teste = y.iloc[
    ponto_corte:
].copy()


dataset_teste = dataset.iloc[
    ponto_corte:
].copy()


print(
    f"Total de amostras: "
    f"{len(dataset)}"
)


print(
    f"Parte inicial: "
    f"{ponto_corte}"
)


print(
    f"Validação: "
    f"{len(X_teste)}"
)


if len(X_teste) < 5:

    raise RuntimeError(
        "O conjunto de validação possui "
        "menos de 5 amostras."
    )


# ============================================================
# 15. GERAR PREVISÕES
# ============================================================

print()
print("=" * 70)
print("GERANDO PREVISÕES DO MODELO REAL")
print("=" * 70)


previsoes = modelo.predict(
    X_teste
)


# ============================================================
# 16. BASELINE
# ============================================================

# Baseline:
#
# prever que daqui a 60 minutos
# o nível será igual ao nível atual.

baseline = (
    X_teste[
        "water_level"
    ]
    .to_numpy()
)


# ============================================================
# 17. MÉTRICAS DO RANDOM FOREST
# ============================================================

mae_modelo = mean_absolute_error(
    y_teste,
    previsoes
)


rmse_modelo = np.sqrt(
    mean_squared_error(
        y_teste,
        previsoes
    )
)


r2_modelo = r2_score(
    y_teste,
    previsoes
)


# ============================================================
# 18. MÉTRICAS DO BASELINE
# ============================================================

mae_baseline = mean_absolute_error(
    y_teste,
    baseline
)


rmse_baseline = np.sqrt(
    mean_squared_error(
        y_teste,
        baseline
    )
)


r2_baseline = r2_score(
    y_teste,
    baseline
)


# ============================================================
# 19. MELHORIA DO MODELO
# ============================================================

if mae_baseline != 0:

    melhoria_mae = (
        (
            mae_baseline
            - mae_modelo
        )
        / mae_baseline
    ) * 100

else:

    melhoria_mae = 0


if rmse_baseline != 0:

    melhoria_rmse = (
        (
            rmse_baseline
            - rmse_modelo
        )
        / rmse_baseline
    ) * 100

else:

    melhoria_rmse = 0


# ============================================================
# 20. RESULTADOS
# ============================================================

print()
print("=" * 70)
print("RESULTADOS DA VALIDAÇÃO REAL")
print("=" * 70)


print()
print("RANDOM FOREST - MODELO REAL")


print(
    f"MAE  : {mae_modelo:.4f} cm"
)


print(
    f"RMSE : {rmse_modelo:.4f} cm"
)


print(
    f"R²   : {r2_modelo:.4f}"
)


print()
print("BASELINE - NÍVEL ATUAL")


print(
    f"MAE  : {mae_baseline:.4f} cm"
)


print(
    f"RMSE : {rmse_baseline:.4f} cm"
)


print(
    f"R²   : {r2_baseline:.4f}"
)


print()
print("MELHORIA DO MODELO SOBRE O BASELINE")


print(
    f"Melhoria MAE : {melhoria_mae:.2f}%"
)


print(
    f"Melhoria RMSE: {melhoria_rmse:.2f}%"
)


# ============================================================
# 21. AMOSTRAS DA VALIDAÇÃO
# ============================================================

print()
print("=" * 70)
print("AMOSTRAS DA VALIDAÇÃO")
print("=" * 70)


resultados = dataset_teste[
    [
        "timestamp",
        "water_level",
        "target_60min"
    ]
].copy()


resultados[
    "nivel_previsto_60min"
] = previsoes


resultados[
    "erro_cm"
] = (
    resultados[
        "nivel_previsto_60min"
    ]
    -
    resultados[
        "target_60min"
    ]
)


resultados[
    "erro_absoluto_cm"
] = (
    resultados[
        "erro_cm"
    ]
    .abs()
)


print()


print(
    resultados[
        [
            "water_level",
            "target_60min",
            "nivel_previsto_60min",
            "erro_absoluto_cm"
        ]
    ]
    .tail(20)
    .to_string(
        index=False
    )
)


# ============================================================
# 22. IMPORTÂNCIA DAS VARIÁVEIS
# ============================================================

print()
print("=" * 70)
print("IMPORTÂNCIA DAS VARIÁVEIS")
print("=" * 70)


if hasattr(
    modelo,
    "feature_importances_"
):

    importancias = (
        modelo.feature_importances_
    )


    for nome, importancia in sorted(
        zip(
            features_modelo,
            importancias
        ),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"{nome:25s}: "
            f"{importancia:.6f}"
        )


# ============================================================
# 23. SALVAR RESULTADOS DETALHADOS
# ============================================================

resultados.to_csv(
    VALIDATION_PATH,
    index=False
)


# ============================================================
# 24. SALVAR RESUMO DAS MÉTRICAS
# ============================================================

resumo_metricas = pd.DataFrame(
    {
        "modelo": [
            "Random Forest",
            "Baseline - nivel atual"
        ],

        "MAE_cm": [
            mae_modelo,
            mae_baseline
        ],

        "RMSE_cm": [
            rmse_modelo,
            rmse_baseline
        ],

        "R2": [
            r2_modelo,
            r2_baseline
        ],

        "melhoria_MAE_percent": [
            melhoria_mae,
            0
        ],

        "melhoria_RMSE_percent": [
            melhoria_rmse,
            0
        ]
    }
)


resumo_metricas.to_csv(
    SUMMARY_PATH,
    index=False
)


# ============================================================
# 25. FINAL
# ============================================================

print()
print("=" * 70)
print("VALIDAÇÃO FINALIZADA")
print("=" * 70)


print()
print("Resultados detalhados:")


print(
    VALIDATION_PATH
)


print()
print("Resumo das métricas:")


print(
    SUMMARY_PATH
)


print()
print("=" * 70)
print("VALIDAÇÃO CONCLUÍDA COM DADOS REAIS DO ESP32")
print("=" * 70)