import argparse
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests


# ============================================================
# FLOODSENSE AI - VERIFICAÇÃO DA COLETA (SOMENTE LEITURA)
#
# Resume a qualidade dos dados que o ESP32 enviou:
#   - quantas leituras, período, intervalo típico;
#   - buracos (pausas) e a maior pausa;
#   - valores inválidos, repetidos e timestamps que não parecem horário real;
#   - mínimo, máximo, desvio padrão e saltos bruscos entre leituras.
#
# Só lê (GET no Firebase ou CSV local). Não escreve nada.
#
# Uso:
#   cd codigo\ia
#   python verificar_coleta.py
#   python verificar_coleta.py --desde 2026-10-23T14:00     (só a sessão nova)
#   python verificar_coleta.py --csv ..\historico_completo_esp32.csv
# ============================================================

FIREBASE_HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
SENSOR_ID = "FS-001"
HISTORY_URL = f"{FIREBASE_HOST}/sensor_history_treinamento/{SENSOR_ID}.json"

# Epoch em segundos plausível: 2020-01-01 até 2100-01-01.
EPOCH_MIN = 1_577_836_800
EPOCH_MAX = 4_102_444_800
SALTO_BRUSCO_CM = 20.0   # variação entre leituras seguidas que merece conferência
SESSAO_GAP_S = 3600      # pausa maior que isso separa uma 'sessão' de coleta da outra
IDADE_MAX_ULTIMA_S = 15 * 60  # última leitura mais velha que isso = coleta parada?


def carregar_firebase(url=HISTORY_URL):
    resposta = requests.get(url, timeout=30)
    resposta.raise_for_status()
    dados = resposta.json()
    if dados is None:
        return pd.DataFrame(columns=["timestamp", "level"]), 0
    if not isinstance(dados, dict):
        raise ValueError(f"Formato inesperado: {type(dados).__name__}")
    linhas, descartados = [], 0
    for chave, valor in dados.items():
        try:
            nivel = float(valor.get("level")) if isinstance(valor, dict) else float("nan")
            try:
                ts = int(chave)
            except ValueError:
                # outros nós podem usar chaves automáticas e guardar o horário no valor
                ts = int(float(valor.get("timestamp")))
                if ts > 100_000_000_000:  # milissegundos
                    ts //= 1000
        except (TypeError, ValueError, AttributeError):
            descartados += 1
            continue
        linhas.append((ts, nivel))
    return pd.DataFrame(linhas, columns=["timestamp", "level"]), descartados


def carregar_csv(caminho):
    df = pd.read_csv(caminho)
    if not {"timestamp", "water_level"}.issubset(df.columns):
        raise ValueError("o CSV precisa das colunas 'timestamp' e 'water_level'")
    return df.rename(columns={"water_level": "level"})[["timestamp", "level"]], 0


def _fmt(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def analisar(df, desde_ts=None, agora=None):
    """Devolve um dicionário com o resumo. Não imprime nada."""
    r = {"total_bruto": int(len(df))}

    df = df.copy()
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["level"] = pd.to_numeric(df["level"], errors="coerce")

    invalidos_nivel = int((~np.isfinite(df["level"])).sum())
    ts_invalidos = int(((df["timestamp"] < EPOCH_MIN) | (df["timestamp"] > EPOCH_MAX)
                        | df["timestamp"].isna()).sum())
    r["nivel_invalido"] = invalidos_nivel
    r["timestamp_fora_de_epoch"] = ts_invalidos

    df = df.dropna(subset=["timestamp", "level"])
    df = df[np.isfinite(df["level"])]
    df = df[(df["timestamp"] >= EPOCH_MIN) & (df["timestamp"] <= EPOCH_MAX)]
    r["repetidos"] = int(df["timestamp"].duplicated().sum())
    df = df.drop_duplicates(subset="timestamp").sort_values("timestamp")

    if desde_ts is not None:
        df = df[df["timestamp"] >= desde_ts]
    r["validas"] = int(len(df))
    if len(df) < 2:
        return r

    ts = df["timestamp"].to_numpy(dtype=np.int64)
    nivel = df["level"].to_numpy(dtype=float)
    dif = np.diff(ts)

    r["inicio"], r["fim"] = int(ts[0]), int(ts[-1])
    r["duracao_h"] = round((ts[-1] - ts[0]) / 3600, 2)
    mediano = float(np.median(dif))
    r["intervalo_mediano_s"] = mediano

    limite_buraco = max(mediano * 3, 60)
    idx = np.where(dif > limite_buraco)[0]
    r["buracos"] = int(len(idx))
    r["maior_buraco_s"] = int(dif.max())
    # os 10 maiores buracos, em ordem cronológica
    maiores = sorted(int(i) for i in np.argsort(dif)[::-1][:10] if dif[i] > limite_buraco)
    r["buracos_lista"] = [(int(ts[i]), int(dif[i])) for i in maiores]

    # sessões: trechos de coleta separados por pausas maiores que SESSAO_GAP_S
    cortes = np.where(dif > SESSAO_GAP_S)[0]
    inicios = np.concatenate(([0], cortes + 1)).astype(int)
    fins = np.concatenate((cortes, [len(ts) - 1])).astype(int)
    r["sessoes"] = [
        {"inicio": int(ts[a]), "fim": int(ts[b]), "leituras": int(b - a + 1),
         "min": round(float(nivel[a:b + 1].min()), 1), "max": round(float(nivel[a:b + 1].max()), 1)}
        for a, b in zip(inicios, fins)
    ]

    # há quanto tempo chegou a última leitura
    agora = int(time.time()) if agora is None else int(agora)
    r["idade_ultima_s"] = agora - int(ts[-1])

    cobertura = len(ts) / (((ts[-1] - ts[0]) / mediano) + 1) if mediano > 0 else float("nan")
    r["cobertura_pct"] = round(min(cobertura, 1.0) * 100, 1)

    r["nivel_min"] = round(float(nivel.min()), 2)
    r["nivel_max"] = round(float(nivel.max()), 2)
    r["nivel_desvio"] = round(float(nivel.std()), 3)
    r["zeros"] = int(np.sum(nivel == 0))

    saltos = np.abs(np.diff(nivel))
    r["saltos_bruscos"] = int(np.sum(saltos >= SALTO_BRUSCO_CM))
    r["maior_salto_cm"] = round(float(saltos.max()), 2)
    return r


def imprimir(r, desde_txt=None):
    print("=" * 70)
    print("FLOODSENSE AI - VERIFICAÇÃO DA COLETA (somente leitura)")
    print("=" * 70)
    if desde_txt:
        print(f"Filtro: leituras a partir de {desde_txt}")
    print(f"Registros lidos: {r['total_bruto']} | válidos: {r['validas']}")
    print(f"Nível inválido: {r['nivel_invalido']} | timestamp fora de horário real: "
          f"{r['timestamp_fora_de_epoch']} | timestamps repetidos: {r['repetidos']}")

    if "inicio" not in r:
        print("\nMenos de 2 leituras válidas: ainda não dá para avaliar a coleta.")
        return

    print(f"\nPeríodo: {_fmt(r['inicio'])}  ->  {_fmt(r['fim'])}  ({r['duracao_h']} h)")
    print(f"Intervalo típico entre leituras: {r['intervalo_mediano_s']:.0f} s")
    print(f"Cobertura (leituras presentes / esperadas): {r['cobertura_pct']}%")
    print(f"Buracos (pausas > 3x o intervalo): {r['buracos']} | maior pausa: "
          f"{r['maior_buraco_s']} s ({r['maior_buraco_s'] / 3600:.1f} h)")
    print("Os 10 maiores buracos (início da pausa):")
    for ts, dur in r["buracos_lista"]:
        print(f"   - a partir de {_fmt(ts)}: {dur / 3600:.1f} h sem leitura")

    sess = r["sessoes"]
    print(f"\nSESSÕES de coleta (separadas por pausas > {SESSAO_GAP_S // 60} min): {len(sess)}")
    for s in sess[-8:]:
        print(f"   - {_fmt(s['inicio'])} -> {_fmt(s['fim'])} | {s['leituras']} leituras "
              f"| nível {s['min']} a {s['max']} cm")
    if len(sess) > 8:
        print(f"   (mostrando as 8 últimas de {len(sess)})")

    idade = r["idade_ultima_s"]
    print(f"\nÚLTIMA LEITURA: {_fmt(r['fim'])}  (há {idade / 3600:.1f} h)")

    print(f"\nNível: mín {r['nivel_min']} cm | máx {r['nivel_max']} cm | "
          f"desvio padrão {r['nivel_desvio']} cm | leituras = 0: {r['zeros']}")
    print(f"Saltos >= {SALTO_BRUSCO_CM:.0f} cm entre leituras seguidas: {r['saltos_bruscos']} "
          f"(maior: {r['maior_salto_cm']} cm)")

    print("\nAVISOS:")
    avisos = []
    if r["idade_ultima_s"] > IDADE_MAX_ULTIMA_S:
        avisos.append(f"a última leitura tem {r['idade_ultima_s'] / 3600:.1f} h: a coleta pode ter parado "
                      "(ESP32 sem Wi-Fi/energia, ou enviando para outro nó do Firebase).")
    if r["timestamp_fora_de_epoch"]:
        avisos.append("há timestamps que não parecem horário real (verifique o NTP do ESP32).")
    if r["nivel_invalido"] or r["zeros"]:
        avisos.append("há níveis inválidos ou iguais a 0 (possível falha de leitura do sensor).")
    if r["buracos"]:
        avisos.append("há pausas na coleta; cada pausa impede exemplos de treino que cruzem o buraco.")
    if r["nivel_desvio"] < 0.5:
        avisos.append("o nível quase não varia: esses dados não ensinam nada sobre subida de água.")
    if r["saltos_bruscos"]:
        avisos.append("há saltos bruscos: confira se são água real ou ruído do sensor.")
    if r["duracao_h"] < 24 * 14:
        avisos.append("menos de 14 dias de coleta: indicativo, não conclusivo (ver recomendação do TCC).")
    print("\n".join(f"  - {a}" for a in avisos) if avisos else "  nenhum.")


def _parse_desde(txt):
    if txt is None:
        return None
    try:
        return int(txt)
    except ValueError:
        pass
    dt = datetime.fromisoformat(txt)
    if dt.tzinfo is None:
        dt = dt.astimezone()  # horário local do computador
    return int(dt.timestamp())


def main(argv=None):
    parser = argparse.ArgumentParser(description="FloodSense AI - verifica a qualidade da coleta")
    parser.add_argument("--csv", type=Path, default=None, help="usa um CSV local em vez do Firebase")
    parser.add_argument("--no", default="sensor_history_treinamento",
                        help="nó do Firebase a analisar (padrão: %(default)s). "
                             "Ex.: sensor_history para ver o outro registro")
    parser.add_argument("--desde", default=None,
                        help="só considera leituras a partir de AAAA-MM-DDTHH:MM (horário local) ou epoch")
    args = parser.parse_args(argv)

    try:
        desde = _parse_desde(args.desde)
    except ValueError:
        print(f"--desde inválido: {args.desde!r}. Use 2026-10-23T14:00 ou um epoch em segundos.")
        return 1

    try:
        if args.csv:
            df, _ = carregar_csv(args.csv)
        else:
            df, _ = carregar_firebase(f"{FIREBASE_HOST}/{args.no}/{SENSOR_ID}.json")
    except requests.exceptions.RequestException as erro:
        print(f"Firebase indisponível ({erro}). Use --csv para analisar um arquivo local.")
        return 1
    except (ValueError, OSError) as erro:
        print(f"Não foi possível ler os dados: {erro}")
        return 1

    if not args.csv:
        print(f"Nó analisado: /{args.no}/{SENSOR_ID}")
    imprimir(analisar(df, desde), args.desde)
    return 0


if __name__ == "__main__":
    sys.exit(main())