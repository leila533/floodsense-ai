from pathlib import Path

import pandas as pd
import numpy as np
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)
from sklearn.model_selection import train_test_split


# ============================================================
# FLOODSENSE AI
# MODELO COMPATÍVEL COM ESP32
# PREVISÃO DO NÍVEL DA ÁGUA 60 MINUTOS À FRENTE
#
# MODELO ORIGINAL:
#   utiliza inlet_flow
#
# ESTE MODELO:
#   utiliza SOMENTE o nível da água e seu histórico
#
# Cada timestep = 5 minutos
# 12 timesteps = 60 minutos
#
# IMPORTANTE:
# O modelo original NÃO será sobrescrito.
# ============================================================


print("=" * 70)
print("FLOODSENSE AI - MODELO COMPATÍVEL COM ESP32")
print("PREVISÃO DO NÍVEL DA ÁGUA EM 60 MINUTOS")
print("=" * 70)


# ============================================================
# 1. CAMINHO DO DATASET
# ============================================================

DATASET = Path(
    r"C:\Users\Victória\Downloads\Dataset_Rerelease\Models\Model_1"
)

TRAIN_DIR = DATASET / "train"

PASTA_CODIGO = Path(__file__).resolve().parent


# ============================================================
# 2. CONFIGURAÇÕES
# ============================================================

HORIZONTE = 12

TEST_SIZE = 0.20

RANDOM_STATE = 42

TIMESTEP_MINUTOS = 5


# ============================================================
# 3. ARQUIVOS DE SAÍDA
#
# TODOS recebem "_esp32" para preservar os resultados
# do modelo anterior.
# ============================================================

MODELO_PATH = (
    PASTA_CODIGO /
    "floodsense_model_60min_esp32.pkl"
)

RESULTADOS_PATH = (
    PASTA_CODIGO /
    "resultados_floodsense_60min_esp32.csv"
)

COMPARACAO_PATH = (
    PASTA_CODIGO /
    "comparacao_floodsense_60min_esp32.csv"
)

IMPORTANCIA_PATH = (
    PASTA_CODIGO /
    "importancia_variaveis_floodsense_esp32.csv"
)

RESUMO_PATH = (
    PASTA_CODIGO /
    "resumo_experimento_floodsense_esp32.csv"
)


# ============================================================
# 4. CARREGAR EVENTOS
# ============================================================

def carregar_eventos(pasta):

    dados = []

    eventos = sorted(
        pasta.glob("event_*")
    )

    print(
        f"\nEncontrados {len(eventos)} eventos em:"
    )

    print(pasta)

    for evento in eventos:

        arquivo = (
            evento /
            "1d_nodes_dynamic_all.csv"
        )

        if not arquivo.exists():

            arquivo = (
                evento /
                "1d_nodes_dynamic_all"
            )

        if not arquivo.exists():

            print(
                f"AVISO: arquivo não encontrado: "
                f"{evento}"
            )

            continue

        try:

            df = pd.read_csv(
                arquivo
            )

            # ------------------------------------------------
            # Para o modelo compatível com ESP32 precisamos
            # somente destas colunas.
            #
            # inlet_flow continua sendo aceito no dataset,
            # mas NÃO será utilizado pelo modelo.
            # ------------------------------------------------

            colunas_necessarias = {
                "timestep",
                "node_idx",
                "water_level"
            }

            if not colunas_necessarias.issubset(
                df.columns
            ):

                print(
                    f"AVISO: colunas inesperadas "
                    f"em {evento.name}: "
                    f"{list(df.columns)}"
                )

                continue

            df["event_id"] = (
                evento.name
            )

            dados.append(df)

            print(
                f"OK: {evento.name} "
                f"-> {len(df):,} registros"
            )

        except Exception as erro:

            print(
                f"ERRO ao ler {evento.name}: "
                f"{erro}"
            )

    if not dados:

        raise RuntimeError(
            "Nenhum evento válido foi encontrado."
        )

    return pd.concat(
        dados,
        ignore_index=True
    )


# ============================================================
# 5. PREPARAR DADOS
# ============================================================

def preparar_dados(df):

    df = df.copy()

    # --------------------------------------------------------
    # ORDENAR TEMPORALMENTE
    # --------------------------------------------------------

    df = df.sort_values(
        [
            "event_id",
            "node_idx",
            "timestep"
        ]
    )

    # --------------------------------------------------------
    # AGRUPAMENTO POR EVENTO E NÓ
    # --------------------------------------------------------

    grupo = df.groupby(
        [
            "event_id",
            "node_idx"
        ]
    )

    # --------------------------------------------------------
    # HISTÓRICO DO NÍVEL DA ÁGUA
    #
    # 1 timestep  = 5 minutos
    # 3 timesteps = 15 minutos
    # 6 timesteps = 30 minutos
    # 12 timesteps = 60 minutos
    # 18 timesteps = 90 minutos
    #
    # Esses dados são compatíveis com a ideia de utilizar
    # somente o histórico de leituras do sensor.
    # --------------------------------------------------------

    df["water_level_lag_1"] = (
        grupo["water_level"]
        .shift(1)
    )

    df["water_level_lag_3"] = (
        grupo["water_level"]
        .shift(3)
    )

    df["water_level_lag_6"] = (
        grupo["water_level"]
        .shift(6)
    )

    df["water_level_lag_12"] = (
        grupo["water_level"]
        .shift(12)
    )

    df["water_level_lag_18"] = (
        grupo["water_level"]
        .shift(18)
    )

    # --------------------------------------------------------
    # ALVO
    #
    # Prever o nível 12 timesteps à frente.
    #
    # 12 x 5 minutos = 60 minutos
    # --------------------------------------------------------

    df["target_water_level_60min"] = (
        grupo["water_level"]
        .shift(-HORIZONTE)
    )

    # --------------------------------------------------------
    # REMOVER REGISTROS INCOMPLETOS
    # --------------------------------------------------------

    colunas_validacao = [

        "water_level_lag_1",

        "water_level_lag_3",

        "water_level_lag_6",

        "water_level_lag_12",

        "water_level_lag_18",

        "target_water_level_60min"
    ]

    df = df.dropna(
        subset=colunas_validacao
    )

    return df


# ============================================================
# 6. CARREGAR EVENTOS
# ============================================================

print("\n" + "=" * 70)

print(
    "CARREGANDO EVENTOS"
)

print("=" * 70)


df_bruto = carregar_eventos(
    TRAIN_DIR
)


print(
    f"\nRegistros brutos encontrados: "
    f"{len(df_bruto):,}"
)


# ============================================================
# 7. IDENTIFICAR EVENTOS
# ============================================================

eventos = sorted(
    df_bruto[
        "event_id"
    ].unique()
)


print(
    f"\nTotal de eventos disponíveis: "
    f"{len(eventos)}"
)


# ============================================================
# 8. DIVISÃO POR EVENTOS
#
# Mantemos a mesma estratégia do modelo original:
# 80% dos eventos para treinamento
# 20% dos eventos para validação
# ============================================================

eventos_treino, eventos_validacao = (
    train_test_split(
        eventos,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE
    )
)


print(
    f"\nEventos utilizados para treinamento: "
    f"{len(eventos_treino)}"
)

print(
    f"Eventos utilizados para validação: "
    f"{len(eventos_validacao)}"
)


# ============================================================
# 9. SEPARAR OS EVENTOS
# ============================================================

df_train_bruto = df_bruto[
    df_bruto[
        "event_id"
    ].isin(eventos_treino)
].copy()


df_validacao_bruto = df_bruto[
    df_bruto[
        "event_id"
    ].isin(eventos_validacao)
].copy()


print(
    f"\nRegistros brutos de treinamento: "
    f"{len(df_train_bruto):,}"
)

print(
    f"Registros brutos de validação: "
    f"{len(df_validacao_bruto):,}"
)


# ============================================================
# 10. PREPARAR TREINAMENTO
# ============================================================

print(
    "\nPreparando dados de treinamento..."
)


df_train = preparar_dados(
    df_train_bruto
)


print(
    f"Registros válidos para treinamento: "
    f"{len(df_train):,}"
)


# ============================================================
# 11. PREPARAR VALIDAÇÃO
# ============================================================

print(
    "\nPreparando dados de validação..."
)


df_validacao = preparar_dados(
    df_validacao_bruto
)


print(
    f"Registros válidos para validação: "
    f"{len(df_validacao):,}"
)


# ============================================================
# 12. VARIÁVEIS DA IA
#
# SOMENTE VARIÁVEIS DISPONÍVEIS A PARTIR DO SENSOR.
#
# NÃO UTILIZAMOS:
#   inlet_flow
#   inlet_flow_lag_1
#   inlet_flow_lag_3
#   inlet_flow_lag_6
#
# Isso torna o modelo adequado para a futura integração
# com o histórico de níveis recebido pelo ESP32/Firebase.
# ============================================================

FEATURES = [

    "water_level",

    "water_level_lag_1",

    "water_level_lag_3",

    "water_level_lag_6",

    "water_level_lag_12",

    "water_level_lag_18"
]


TARGET = (
    "target_water_level_60min"
)


print("\nVariáveis utilizadas pelo modelo ESP32:")

for feature in FEATURES:

    print(
        f" - {feature}"
    )

print(
    f"\nTotal de variáveis: "
    f"{len(FEATURES)}"
)


# ============================================================
# 13. MATRIZES
# ============================================================

X_train = df_train[
    FEATURES
]

y_train = df_train[
    TARGET
]


X_validacao = df_validacao[
    FEATURES
]

y_validacao = df_validacao[
    TARGET
]


print(
    f"\nQuantidade de amostras para treinamento: "
    f"{len(X_train):,}"
)

print(
    f"Quantidade de amostras para validação: "
    f"{len(X_validacao):,}"
)


# ============================================================
# 14. TREINAMENTO RANDOM FOREST
# ============================================================

print("\n" + "=" * 70)

print(
    "TREINANDO RANDOM FOREST - MODELO ESP32"
)

print("=" * 70)


modelo = RandomForestRegressor(

    n_estimators=100,

    max_depth=20,

    min_samples_leaf=2,

    random_state=RANDOM_STATE,

    n_jobs=-1
)


modelo.fit(
    X_train,
    y_train
)


print(
    "\nTreinamento concluído!"
)


# ============================================================
# 15. PREVISÕES
# ============================================================

print(
    "\nGerando previsões para "
    "60 minutos à frente..."
)


previsoes = modelo.predict(
    X_validacao
)


# ============================================================
# 16. BASELINE
#
# Estratégia simples:
# considerar que o nível daqui a 60 minutos
# será igual ao nível atual.
# ============================================================

baseline = df_validacao[
    "water_level"
].values


# ============================================================
# 17. MÉTRICAS DO RANDOM FOREST
# ============================================================

mae_modelo = mean_absolute_error(
    y_validacao,
    previsoes
)


rmse_modelo = np.sqrt(
    mean_squared_error(
        y_validacao,
        previsoes
    )
)


r2_modelo = r2_score(
    y_validacao,
    previsoes
)


# ============================================================
# 18. MÉTRICAS DO BASELINE
# ============================================================

mae_baseline = mean_absolute_error(
    y_validacao,
    baseline
)


rmse_baseline = np.sqrt(
    mean_squared_error(
        y_validacao,
        baseline
    )
)


r2_baseline = r2_score(
    y_validacao,
    baseline
)


# ============================================================
# 19. RESULTADOS
# ============================================================

print("\n" + "=" * 70)

print(
    "RESULTADOS - MODELO COMPATÍVEL COM ESP32"
)

print("=" * 70)


print(
    "\nRANDOM FOREST - ESP32"
)


print(
    f"MAE  : {mae_modelo:.6f}"
)


print(
    f"RMSE : {rmse_modelo:.6f}"
)


print(
    f"R²   : {r2_modelo:.6f}"
)


print(
    "\nBASELINE - NÍVEL ATUAL"
)


print(
    f"MAE  : {mae_baseline:.6f}"
)


print(
    f"RMSE : {rmse_baseline:.6f}"
)


print(
    f"R²   : {r2_baseline:.6f}"
)


# ============================================================
# 20. IMPORTÂNCIA DAS VARIÁVEIS
# ============================================================

print("\n" + "=" * 70)

print(
    "IMPORTÂNCIA DAS VARIÁVEIS"
)

print("=" * 70)


importancias = (
    modelo.feature_importances_
)


for nome, importancia in sorted(

    zip(
        FEATURES,
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
# 21. SALVAR MODELO
#
# IMPORTANTE:
# NÃO sobrescreve floodsense_model_60min.pkl
#
# O novo arquivo será:
# floodsense_model_60min_esp32.pkl
# ============================================================

modelo_completo = {

    "modelo": modelo,

    "features": FEATURES,

    "target": TARGET,

    "horizonte_minutos": 60,

    "timestep_minutos": TIMESTEP_MINUTOS,

    "historico_maximo_minutos": 90,

    "tipo_modelo": "Random Forest",

    "compatibilidade": "ESP32",

    "entrada_principal": "water_level",

    "observacao": (
        "Modelo treinado somente com histórico "
        "do nível da água. Não utiliza inlet_flow."
    )

}


joblib.dump(
    modelo_completo,
    MODELO_PATH
)


print(
    f"\nModelo ESP32 salvo em:"
    f"\n{MODELO_PATH}"
)


# ============================================================
# 22. RESULTADOS DETALHADOS
# ============================================================

resultados = pd.DataFrame({

    "evento":
        df_validacao[
            "event_id"
        ].values,

    "node_idx":
        df_validacao[
            "node_idx"
        ].values,

    "nivel_real_60min":
        y_validacao.values,

    "nivel_previsto_60min":
        previsoes,

    "nivel_atual":
        df_validacao[
            "water_level"
        ].values,

    "erro":
        y_validacao.values -
        previsoes

})


resultados.to_csv(
    RESULTADOS_PATH,
    index=False
)


print(
    f"\nResultados detalhados salvos em:"
    f"\n{RESULTADOS_PATH}"
)


# ============================================================
# 23. COMPARAÇÃO
# ============================================================

comparacao = pd.DataFrame({

    "modelo": [

        "Random Forest - ESP32 - 60 minutos",

        "Baseline - nível atual"

    ],

    "MAE": [

        mae_modelo,

        mae_baseline

    ],

    "RMSE": [

        rmse_modelo,

        rmse_baseline

    ],

    "R2": [

        r2_modelo,

        r2_baseline

    ]

})


comparacao.to_csv(
    COMPARACAO_PATH,
    index=False
)


print(
    f"\nComparação salva em:"
    f"\n{COMPARACAO_PATH}"
)


# ============================================================
# 24. IMPORTÂNCIA DAS VARIÁVEIS EM CSV
# ============================================================

importancia_df = pd.DataFrame({

    "variavel":
        FEATURES,

    "importancia":
        importancias

})


importancia_df = (
    importancia_df
    .sort_values(
        "importancia",
        ascending=False
    )
)


importancia_df.to_csv(
    IMPORTANCIA_PATH,
    index=False
)


print(
    f"\nImportância das variáveis salva em:"
    f"\n{IMPORTANCIA_PATH}"
)


# ============================================================
# 25. RESUMO DO EXPERIMENTO
# ============================================================

resumo = pd.DataFrame({

    "informacao": [

        "Tipo do modelo",

        "Compatibilidade",

        "Total de eventos",

        "Eventos de treinamento",

        "Eventos de validação",

        "Amostras de treinamento",

        "Amostras de validação",

        "Quantidade de variáveis",

        "Timestep",

        "Horizonte da previsão",

        "Histórico máximo utilizado",

        "Variáveis utilizadas",

        "MAE Random Forest",

        "RMSE Random Forest",

        "R2 Random Forest",

        "MAE Baseline",

        "RMSE Baseline",

        "R2 Baseline"

    ],

    "valor": [

        "Random Forest",

        "ESP32",

        len(eventos),

        len(eventos_treino),

        len(eventos_validacao),

        len(df_train),

        len(df_validacao),

        len(FEATURES),

        "5 minutos",

        "60 minutos",

        "90 minutos",

        ", ".join(FEATURES),

        mae_modelo,

        rmse_modelo,

        r2_modelo,

        mae_baseline,

        rmse_baseline,

        r2_baseline

    ]

})


resumo.to_csv(
    RESUMO_PATH,
    index=False
)


print(
    f"\nResumo do experimento salvo em:"
    f"\n{RESUMO_PATH}"
)


# ============================================================
# 26. VALIDAÇÃO DA ESTRUTURA DO MODELO
# ============================================================

print("\n" + "=" * 70)

print(
    "VERIFICANDO MODELO SALVO"
)

print("=" * 70)


modelo_teste = joblib.load(
    MODELO_PATH
)


print(
    f"\nTipo do arquivo carregado: "
    f"{type(modelo_teste).__name__}"
)


print(
    "\nChaves do modelo:"
)


for chave in modelo_teste.keys():

    print(
        f" - {chave}"
    )


print(
    "\nFeatures finais:"
)


for feature in modelo_teste["features"]:

    print(
        f" - {feature}"
    )


print(
    f"\nHorizonte: "
    f"{modelo_teste['horizonte_minutos']} minutos"
)


print(
    f"Timestep: "
    f"{modelo_teste['timestep_minutos']} minutos"
)


print(
    f"Compatibilidade: "
    f"{modelo_teste['compatibilidade']}"
)


# ============================================================
# 27. FINAL
# ============================================================

print("\n" + "=" * 70)

print(
    "TREINAMENTO DO MODELO ESP32 FINALIZADO"
)

print("=" * 70)


print(
    "\nArquivos gerados:"
)

print(
    f"\nModelo:"
    f"\n{MODELO_PATH}"
)

print(
    f"\nResultados:"
    f"\n{RESULTADOS_PATH}"
)

print(
    f"\nComparação:"
    f"\n{COMPARACAO_PATH}"
)

print(
    f"\nImportância:"
    f"\n{IMPORTANCIA_PATH}"
)

print(
    f"\nResumo:"
    f"\n{RESUMO_PATH}"
)


print(
    "\nModelo original preservado:"
)

print(
    PASTA_CODIGO /
    "floodsense_model_60min.pkl"
)


print(
    "\nFloodSense AI - "
    "modelo compatível com ESP32 concluído!"
)