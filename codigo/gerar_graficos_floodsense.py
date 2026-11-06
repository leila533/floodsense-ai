import pandas as pd
import matplotlib.pyplot as plt
import joblib
from pathlib import Path


# ============================================================
# FLOODSENSE AI
# GERAÇÃO DOS GRÁFICOS DOS RESULTADOS DA IA
# ============================================================

BASE = Path(__file__).parent

arquivo_resultados = BASE / "resultados_floodsense_60min.csv"
arquivo_comparacao = BASE / "comparacao_floodsense_60min.csv"
arquivo_modelo = BASE / "floodsense_model_60min.pkl"

pasta_graficos = BASE / "graficos_ia"
pasta_graficos.mkdir(exist_ok=True)


print("=" * 70)
print("FLOODSENSE AI - GERAÇÃO DOS GRÁFICOS")
print("=" * 70)


# ============================================================
# 1. CARREGAR RESULTADOS
# ============================================================

df = pd.read_csv(arquivo_resultados)

print(f"\nRegistros carregados: {len(df):,}")

print("\nColunas encontradas:")
print(list(df.columns))


# ============================================================
# 2. GRÁFICO REAL x PREVISTO
# ============================================================
#
# IMPORTANTE:
# O resultado possui vários eventos e vários nós.
# Não devemos juntar todos eles em uma única linha,
# pois isso cria saltos artificiais no gráfico.
#
# Por isso, selecionamos um único evento e um único nó.
# ============================================================

evento = df["evento"].iloc[0]
node_idx = df["node_idx"].iloc[0]

amostra = df[
    (df["evento"] == evento) &
    (df["node_idx"] == node_idx)
].copy()


# Ordena pelas ocorrências do conjunto de dados
amostra = amostra.reset_index(drop=True)


# Limita a quantidade de pontos para facilitar a visualização
amostra = amostra.head(150)


print("\nAmostra utilizada no gráfico 1:")
print(f"Evento: {evento}")
print(f"Nó: {node_idx}")
print(f"Quantidade de pontos: {len(amostra)}")


plt.figure(figsize=(12, 6))


plt.plot(
    range(len(amostra)),
    amostra["nivel_real_60min"].values,
    label="Nível real após 60 minutos",
    linewidth=2
)


plt.plot(
    range(len(amostra)),
    amostra["nivel_previsto_60min"].values,
    label="Nível previsto pela IA",
    linestyle="--",
    linewidth=2
)


plt.xlabel(
    "Amostras consecutivas do mesmo nó"
)

plt.ylabel(
    "Nível da água"
)

plt.title(
    "FloodSense AI — Nível real x previsão para 60 minutos\n"
    f"Evento: {evento} | Nó: {node_idx}"
)


plt.legend()

plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


arquivo = pasta_graficos / "01_nivel_real_vs_previsto.png"

plt.savefig(
    arquivo,
    dpi=300
)

plt.close()

print(f"\nGráfico salvo: {arquivo}")


# ============================================================
# 3. DISTRIBUIÇÃO DOS ERROS
# ============================================================

plt.figure(figsize=(10, 6))


plt.hist(
    df["erro"],
    bins=50
)


plt.axvline(
    0,
    linestyle="--",
    linewidth=2
)


plt.xlabel(
    "Erro de previsão"
)

plt.ylabel(
    "Frequência"
)

plt.title(
    "FloodSense AI — Distribuição dos erros de previsão"
)


plt.grid(
    True,
    alpha=0.3
)

plt.tight_layout()


arquivo = pasta_graficos / "02_distribuicao_erros.png"

plt.savefig(
    arquivo,
    dpi=300
)

plt.close()

print(f"Gráfico salvo: {arquivo}")


# ============================================================
# 4. COMPARAÇÃO RANDOM FOREST x BASELINE
# ============================================================

comparacao = pd.read_csv(
    arquivo_comparacao
)


print("\nComparação:")
print(comparacao)


# ============================================================
# 4.1 MAE
# ============================================================

plt.figure(figsize=(8, 5))


plt.bar(
    comparacao["modelo"],
    comparacao["MAE"]
)


plt.ylabel(
    "MAE"
)

plt.title(
    "Comparação de MAE — FloodSense AI"
)


plt.xticks(
    rotation=15
)


plt.grid(
    axis="y",
    alpha=0.3
)

plt.tight_layout()


arquivo = pasta_graficos / "03_comparacao_mae.png"

plt.savefig(
    arquivo,
    dpi=300
)

plt.close()

print(f"Gráfico salvo: {arquivo}")


# ============================================================
# 4.2 RMSE
# ============================================================

plt.figure(figsize=(8, 5))


plt.bar(
    comparacao["modelo"],
    comparacao["RMSE"]
)


plt.ylabel(
    "RMSE"
)

plt.title(
    "Comparação de RMSE — FloodSense AI"
)


plt.xticks(
    rotation=15
)


plt.grid(
    axis="y",
    alpha=0.3
)

plt.tight_layout()


arquivo = pasta_graficos / "04_comparacao_rmse.png"

plt.savefig(
    arquivo,
    dpi=300
)

plt.close()

print(f"Gráfico salvo: {arquivo}")


# ============================================================
# 5. IMPORTÂNCIA DAS VARIÁVEIS
# ============================================================

print(
    "\nGerando gráfico de importância das variáveis..."
)


try:

    # --------------------------------------------------------
    # Carrega o modelo atualizado
    # --------------------------------------------------------

    pacote_modelo = joblib.load(
        arquivo_modelo
    )


    # --------------------------------------------------------
    # O novo treinamento salva:
    #
    # {
    #     "modelo": modelo,
    #     "features": features,
    #     "target": target,
    #     "horizonte_minutos": 60,
    #     "timestep_minutos": 5
    # }
    # --------------------------------------------------------

    modelo = pacote_modelo["modelo"]

    features = pacote_modelo["features"]


    print(
        "\nVariáveis utilizadas pelo modelo:"
    )


    for feature in features:

        print(
            f" - {feature}"
        )


    # --------------------------------------------------------
    # Importâncias
    # --------------------------------------------------------

    importancias = modelo.feature_importances_


    # --------------------------------------------------------
    # Verificação de segurança
    # --------------------------------------------------------

    if len(features) != len(importancias):

        raise ValueError(
            "Quantidade de variáveis diferente da "
            "quantidade de importâncias fornecidas pelo modelo."
        )


    # --------------------------------------------------------
    # DataFrame das importâncias
    # --------------------------------------------------------

    dados_importancia = pd.DataFrame({

        "variavel": features,

        "importancia": importancias

    })


    dados_importancia = dados_importancia.sort_values(
        "importancia",
        ascending=True
    )


    # --------------------------------------------------------
    # Gráfico
    # --------------------------------------------------------

    plt.figure(
        figsize=(10, 7)
    )


    plt.barh(
        dados_importancia["variavel"],
        dados_importancia["importancia"]
    )


    plt.xlabel(
        "Importância"
    )


    plt.ylabel(
        "Variável"
    )


    plt.title(
        "FloodSense AI — Importância das variáveis\n"
        "Random Forest — previsão em 60 minutos"
    )


    plt.grid(
        axis="x",
        alpha=0.3
    )


    plt.tight_layout()


    arquivo = (
        pasta_graficos /
        "05_importancia_variaveis.png"
    )


    plt.savefig(
        arquivo,
        dpi=300
    )


    plt.close()


    print(
        f"Gráfico salvo: {arquivo}"
    )


except Exception as erro:

    print(
        "\nNão foi possível gerar o gráfico "
        "de importância:"
    )

    print(erro)


# ============================================================
# FINAL
# ============================================================

print(
    "\n" + "=" * 70
)

print(
    "GRÁFICOS GERADOS COM SUCESSO"
)

print(
    "=" * 70
)


print(
    "\nPasta:"
)

print(
    pasta_graficos
)


print(
    "\nArquivos:"
)

print(
    "01_nivel_real_vs_previsto.png"
)

print(
    "02_distribuicao_erros.png"
)

print(
    "03_comparacao_mae.png"
)

print(
    "04_comparacao_rmse.png"
)

print(
    "05_importancia_variaveis.png"
)


print(
    "\nProcesso finalizado."
)