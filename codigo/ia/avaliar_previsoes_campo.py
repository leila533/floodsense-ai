import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests


# ============================================================
# FLOODSENSE AI - AVALIAÇÃO DAS PREVISÕES EM CAMPO (SOMENTE LEITURA)
#
# Compara cada previsão registrada por monitorar_previsoes_campo.py
# com o nível REAL medido 60 min depois (leitura mais próxima dentro
# de ±2 min, mesma regra do treinamento) e calcula:
#
#   - MAE e RMSE do modelo;
#   - MAE do baseline (repetir o nível atual) e a melhoria sobre ele;
#   - acertos de status (normal/warning/critical) e alertas subestimados
#     (o nível real caiu numa faixa MAIS grave que a prevista).
#
# Resultado por modo de previsão (STARTUP, LAG_5, LAG_15, FULL) e geral.
# Previsões cujo +60 min ainda não aconteceu ficam como "pendentes";
# as que não têm leitura real na janela ficam como "sem leitura".
#
# Só lê (GET no Firebase ou CSV local). Não escreve no Firebase.
#
# Uso:
#   cd codigo\ia
#   python avaliar_previsoes_campo.py
#   python avaliar_previsoes_campo.py --historico-csv ..\historico_completo_esp32.csv
# ============================================================

PASTA_CODIGO = Path(__file__).resolve().parent.parent

FIREBASE_HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
SENSOR_ID = "FS-001"
HISTORY_URL = f"{FIREBASE_HOST}/sensor_history_treinamento/{SENSOR_ID}.json"

LOG_PATH = PASTA_CODIGO / "previsoes_campo_log.csv"
SAIDA_PATH = PASTA_CODIGO / "avaliacao_campo_pares.csv"

HORIZONTE_S = 60 * 60
TOLERANCIA_S = 2 * 60

# Mesmos limites do dashboard e do serviço (normal < 60; warning 60-<90; critical >= 90).
LIMITE_WARNING_CM = 60.0
LIMITE_CRITICAL_CM = 90.0
RANK_STATUS = {"normal": 0, "warning": 1, "critical": 2}


def status_de(nivel_cm):
    if nivel_cm >= LIMITE_CRITICAL_CM:
        return "critical"
    if nivel_cm >= LIMITE_WARNING_CM:
        return "warning"
    return "normal"


# ------------------------------------------------------------
# Leitura do histórico real
# ------------------------------------------------------------

def historico_do_firebase(url=HISTORY_URL):
    resposta = requests.get(url, timeout=30)
    resposta.raise_for_status()
    dados = resposta.json()
    if dados is None:
        return np.array([], dtype=np.int64), np.array([], dtype=float)
    if not isinstance(dados, dict):
        raise ValueError(f"Formato inesperado no histórico: {type(dados).__name__}")

    registros = {}
    for chave, valor in dados.items():
        if not isinstance(valor, dict):
            continue
        try:
            nivel = float(valor.get("level"))
            ts = int(chave)
        except (TypeError, ValueError):
            continue
        if math.isfinite(nivel):
            registros[ts] = nivel
    return _ordenar(registros)


def historico_do_csv(caminho):
    df = pd.read_csv(caminho)
    if not {"timestamp", "water_level"}.issubset(df.columns):
        raise ValueError(f"{caminho} precisa das colunas 'timestamp' e 'water_level'")
    df = df.dropna(subset=["timestamp", "water_level"])
    df = df[np.isfinite(df["water_level"].astype(float))]
    return _ordenar(dict(zip(df["timestamp"].astype(np.int64), df["water_level"].astype(float))))


def _ordenar(registros):
    ts = np.array(sorted(registros), dtype=np.int64)
    niveis = np.array([registros[t] for t in ts], dtype=float)
    return ts, niveis


# ------------------------------------------------------------
# Pareamento previsão x realidade
# ------------------------------------------------------------

def parear(log_df, ts, niveis, horizonte_s=HORIZONTE_S, tolerancia_s=TOLERANCIA_S):
    """
    Uma linha por previsão, com estado:
      pareado     -> existe leitura real em alvo ± tolerância (a mais próxima do alvo)
      pendente    -> a janela do alvo ainda não fechou no histórico
      sem_leitura -> a janela fechou e não há leitura real nela
    """
    ultimo = int(ts[-1]) if len(ts) else None
    linhas = []

    for linha in log_df.itertuples(index=False):
        t0 = int(linha.reading_timestamp)
        alvo = t0 + horizonte_s
        registro = {
            "reading_timestamp": t0,
            "prediction_mode": getattr(linha, "prediction_mode", ""),
            "current_level_cm": float(linha.current_level_cm),
            "predicted_level_60min_cm": float(linha.predicted_level_60min_cm),
            "real_level_60min_cm": np.nan,
            "real_timestamp": np.nan,
            "estado": "",
        }

        if ultimo is None or ultimo < alvo + tolerancia_s:
            registro["estado"] = "pendente"
        else:
            esq = int(np.searchsorted(ts, alvo - tolerancia_s, side="left"))
            dire = int(np.searchsorted(ts, alvo + tolerancia_s, side="right"))
            melhor, menor = None, None
            for j in range(esq, dire):
                if int(ts[j]) <= t0:
                    continue
                dist = abs(int(ts[j]) - alvo)
                if menor is None or dist < menor:
                    melhor, menor = j, dist
            if melhor is None:
                registro["estado"] = "sem_leitura"
            else:
                registro["estado"] = "pareado"
                registro["real_level_60min_cm"] = float(niveis[melhor])
                registro["real_timestamp"] = int(ts[melhor])

        linhas.append(registro)

    return pd.DataFrame(linhas)


# ------------------------------------------------------------
# Métricas
# ------------------------------------------------------------

def _metricas_grupo(g):
    prev = g["predicted_level_60min_cm"].to_numpy(float)
    atual = g["current_level_cm"].to_numpy(float)
    real = g["real_level_60min_cm"].to_numpy(float)

    erro = prev - real
    mae = float(np.mean(np.abs(erro)))
    rmse = float(np.sqrt(np.mean(erro ** 2)))
    mae_base = float(np.mean(np.abs(atual - real)))
    melhoria = (mae_base - mae) / mae_base * 100 if mae_base > 0 else float("nan")

    rank_prev = np.array([RANK_STATUS[status_de(v)] for v in prev])
    rank_real = np.array([RANK_STATUS[status_de(v)] for v in real])

    return {
        "pares": int(len(g)),
        "mae_modelo_cm": round(mae, 3),
        "rmse_modelo_cm": round(rmse, 3),
        "mae_baseline_cm": round(mae_base, 3),
        "melhoria_mae_pct": round(melhoria, 2) if math.isfinite(melhoria) else float("nan"),
        "status_acertos_pct": round(float(np.mean(rank_prev == rank_real)) * 100, 1),
        "alertas_subestimados": int(np.sum(rank_real > rank_prev)),
        "alertas_superestimados": int(np.sum(rank_real < rank_prev)),
    }


def calcular_metricas(pares):
    pareados = pares[pares["estado"] == "pareado"]
    if pareados.empty:
        return pd.DataFrame()

    linhas = []
    for modo, g in pareados.groupby("prediction_mode", dropna=False):
        linhas.append({"modo": modo or "(sem modo)", **_metricas_grupo(g)})
    linhas.append({"modo": "TODOS", **_metricas_grupo(pareados)})
    return pd.DataFrame(linhas)


def contagens(pares):
    return {estado: int((pares["estado"] == estado).sum())
            for estado in ("pareado", "pendente", "sem_leitura")}


# ------------------------------------------------------------
# Programa
# ------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="FloodSense AI - avalia as previsões registradas em campo")
    parser.add_argument("--log", type=Path, default=LOG_PATH,
                        help="CSV do monitor (padrão: %(default)s)")
    parser.add_argument("--historico-csv", type=Path, default=None,
                        help="usa um CSV local (timestamp,water_level) em vez do Firebase")
    parser.add_argument("--saida", type=Path, default=SAIDA_PATH,
                        help="CSV com os pares previsão x real (padrão: %(default)s)")
    args = parser.parse_args(argv)

    print("=" * 70)
    print("FLOODSENSE AI - AVALIAÇÃO DAS PREVISÕES EM CAMPO (somente leitura)")
    print("=" * 70)

    if not args.log.exists():
        print(f"Registro não encontrado: {args.log}")
        print("Rode antes o monitor: python monitorar_previsoes_campo.py")
        return 1

    log_df = pd.read_csv(args.log)
    obrigatorias = {"reading_timestamp", "current_level_cm", "predicted_level_60min_cm"}
    if not obrigatorias.issubset(log_df.columns):
        print(f"Registro inválido: faltam colunas {sorted(obrigatorias - set(log_df.columns))}")
        return 1
    log_df = log_df.dropna(subset=list(obrigatorias))
    print(f"Previsões registradas: {len(log_df)}")

    if args.historico_csv:
        ts, niveis = historico_do_csv(args.historico_csv)
        print(f"Histórico real: {len(ts)} leituras (CSV {args.historico_csv})")
    else:
        try:
            ts, niveis = historico_do_firebase()
        except requests.exceptions.RequestException as erro:
            print(f"Firebase indisponível ({erro}). Use --historico-csv para avaliar offline.")
            return 1
        print(f"Histórico real: {len(ts)} leituras (Firebase /sensor_history_treinamento)")

    pares = parear(log_df, ts, niveis)
    pares.to_csv(args.saida, index=False)
    c = contagens(pares)
    print(f"Pareadas: {c['pareado']} | Pendentes (+60 min ainda não ocorreu): {c['pendente']} "
          f"| Sem leitura real na janela ±2 min: {c['sem_leitura']}")

    metricas = calcular_metricas(pares)
    if metricas.empty:
        print("\nAinda não há pares previsão x realidade. Deixe o serviço e o monitor "
              "rodando por mais de 1 hora e rode de novo.")
        return 0

    print("\nERRO DO MODELO vs. BASELINE (repetir o nível atual), em cm:")
    print(metricas.to_string(index=False))
    print(f"\nPares gravados em: {args.saida}")

    n = int(metricas.loc[metricas["modo"] == "TODOS", "pares"].iloc[0])
    if n < 30:
        print(f"\nATENÇÃO: só {n} pares. Com tão poucos, as métricas são indicativas, não conclusivas.")
    print("Estes números vêm de dados REAIS do ESP32; não são comparáveis com o teste simulado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())