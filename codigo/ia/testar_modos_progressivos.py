import contextlib
import copy
import importlib.util
import io
import os
import runpy
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import previsao_floodsense_corrigido as svc  # noqa: E402


# ============================================================
# FLOODSENSE AI - SUÍTE DE TESTES DO SERVIÇO V4 PROGRESSIVO
#
# ESCOPO: TESTES SIMULADOS. Usa o .pkl REAL e o código REAL do serviço,
# mas substitui o Firebase (requests.get/patch) e o relógio de espera
# (time.sleep). NÃO valida o ESP32 físico, o sensor AJ-SR04M, a
# gravação real no Firebase nem o dashboard (ver lista no final).
#
# Garantias da suíte:
#   - nunca acessa a rede real (qualquer tentativa vira FALHA);
#   - não grava no .pkl nem em nenhum arquivo do projeto;
#   - cada teste é isolado: uma exceção só reprova aquele teste;
#   - valores esperados vêm de CONSTANTES LITERAIS (rota, sensor,
#     horizonte, limites) ou do próprio pacote atual (MAE/RMSE), nunca
#     de constantes do serviço que o teste deveria vigiar;
#   - termina com contagem de aprovados / falhos / não executados.
#
# Execução (a partir da raiz do projeto):
#   cd codigo/ia && python testar_modos_progressivos.py
# Códigos de saída: 0 = tudo executado e aprovado; 1 = há falhas;
#                   2 = sem falhas, mas há testes NÃO executados.
# ============================================================

HOST = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
URL_HISTORICO = HOST + "/sensor_history_treinamento/FS-001.json"
URL_HISTORICO_PROIBIDO = "/sensor_history/"
URL_PREVISAO = HOST + "/ai_predictions/FS-001.json"

AGORA = int(time.time())

RESUMO_CSV = AQUI.parent / "resumo_modelos_progressivos.csv"
TREINO_PY = AQUI / "treinar_modelo_real_esp32_v4_progressivo.py"

# Referência histórica de um treinamento ANTIGO. Só informativa.
MAE_REFERENCIA_ANTIGA = {
    "STARTUP": 16.199921, "LAG_5": 10.284384,
    "LAG_15": 8.331515, "FULL": 8.952242,
}

CAMPOS_DASHBOARD = {
    "current_level_cm", "predicted_level_60min_cm", "generated_at",
    "horizon_minutes", "model", "sensor_unit", "real_sensor_compatible",
    "status",
}
CAMPOS_V4 = {
    "prediction_mode", "available_lags", "model_algorithm", "model_version",
    "sensor_id", "reading_timestamp", "selection_metric",
    "selection_mae_test_cm", "initial_fallback",
}

VALORES_POR_MODO = {
    "STARTUP": {"water_level": 200.0},
    "LAG_5": {"water_level": 200.0, "water_level_lag_1": 195.0},
    "LAG_15": {"water_level": 200.0, "water_level_lag_1": 195.0,
               "water_level_lag_3": 185.0},
    "FULL": {"water_level": 200.0, "water_level_lag_1": 195.0,
             "water_level_lag_3": 185.0, "water_level_lag_6": 170.0},
}
LAGS_POR_MODO = {
    "STARTUP": [], "LAG_5": ["5min"], "LAG_15": ["5min", "15min"],
    "FULL": ["5min", "15min", "30min"],
}
COM_LAGS = ["LAG_5", "LAG_15", "FULL"]
ORDEM = ["FULL", "LAG_15", "LAG_5", "STARTUP"]


# ------------------------------------------------------------
# Infraestrutura de teste
# ------------------------------------------------------------

class NaoExecutado(Exception):
    """O teste não pôde rodar (falta de arquivo/insumo); não é aprovação."""


RESULTADOS = []  # (status, nome, detalhe)


def rodar(nome, fn):
    try:
        r = fn()
        ok, det = r if isinstance(r, tuple) else (bool(r), "")
        status = "PASSOU" if ok else "FALHOU"
    except NaoExecutado as e:
        status, det = "NAO EXECUTADO", str(e)
    except Exception as e:  # noqa: BLE001 - isolar cada teste
        status = "FALHOU"
        det = f"{type(e).__name__}: {e} | {traceback.format_exc().splitlines()[-3].strip()}"
    RESULTADOS.append((status, nome, det))
    print(f"{status} | {nome}")
    if det and status != "PASSOU":
        print(f"      -> {det}")
    elif det:
        print(f"      {det}")


class Resp:
    def __init__(self, status=200, dados=None):
        self.status_code = status
        self._d = dados

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} simulado")


@contextlib.contextmanager
def ambiente(get=None, patch=None, sleep=None):
    """
    Substitui requests.get/patch e time.sleep. Registra chamadas e BLOQUEIA
    a rede real: qualquer tentativa de envio HTTP real reprova o teste.
    """
    ch = {"get": [], "patch": [], "sleep": [], "rede_real": []}

    def get_(url, **k):
        ch["get"].append(url)
        if get is None:
            raise AssertionError("teste não definiu resposta para GET")
        return get(url, **k)

    def patch_(url, json=None, **k):
        ch["patch"].append((url, json))
        if patch is None:
            return Resp(200, {})
        return patch(url, json=json, **k)

    sleep_original = time.sleep
    arquivo_servico = os.path.normcase(os.path.realpath(svc.__file__))

    def sleep_(segundos):
        # Só interceptamos esperas chamadas PELO SERVIÇO. Bibliotecas (por
        # exemplo o joblib dentro de RandomForest com n_jobs=-1, que faz
        # time.sleep(0.01) em polling) seguem com o sleep original.
        chamador = sys._getframe(1).f_code.co_filename
        if os.path.normcase(os.path.realpath(chamador)) != arquivo_servico:
            return sleep_original(segundos)
        ch["sleep"].append(segundos)
        if sleep is not None:
            sleep(segundos, ch)
        if len(ch["sleep"]) > 50:
            raise RuntimeError("loop sem fim detectado pelo teste")

    def envio_real(self, request, **k):
        ch["rede_real"].append(request.url)
        raise AssertionError(f"REDE REAL BLOQUEADA: {request.url}")

    orig = (requests.get, requests.patch, time.sleep,
            requests.adapters.HTTPAdapter.send)
    requests.get, requests.patch, time.sleep = get_, patch_, sleep_
    requests.adapters.HTTPAdapter.send = envio_real
    try:
        yield ch
    finally:
        (requests.get, requests.patch, time.sleep,
         requests.adapters.HTTPAdapter.send) = orig
    if ch["rede_real"]:
        raise AssertionError(f"tentativa de rede real: {ch['rede_real']}")


def fb_hist(offsets_min, agora=None, nivel=lambda m: 200.0 - m):
    agora = int(time.time()) if agora is None else int(agora)
    return {str(agora - int(m * 60)): {"level": nivel(m)} for m in offsets_min}


def df_hist(offsets_min):
    linhas = [{"timestamp": AGORA - int(m * 60), "water_level": 200.0 - m}
              for m in offsets_min]
    return pd.DataFrame(linhas).sort_values("timestamp").reset_index(drop=True)


def rodar_ciclo(hist, patch=None, **kw):
    with ambiente(get=lambda u, **k: Resp(200, hist), patch=patch) as ch:
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            ret = svc.ciclo_seguro(**kw)
    return ret, ch, saida.getvalue()


def rodar_main(argv, get, patch=None, max_sleeps=None):
    """Executa o serviço como '__main__' (inclui o tratamento de Ctrl+C)."""
    def sleep_(segundos, ch):
        if max_sleeps is not None and len(ch["sleep"]) >= max_sleeps:
            raise KeyboardInterrupt

    saida, codigo = io.StringIO(), "sem SystemExit"
    antigo = sys.argv
    sys.argv = ["previsao_floodsense_corrigido.py"] + list(argv)
    try:
        with ambiente(get=get, patch=patch, sleep=sleep_) as ch:
            with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
                try:
                    runpy.run_path(str(Path(svc.__file__)), run_name="__main__")
                except SystemExit as e:
                    codigo = e.code
    finally:
        sys.argv = antigo
    return ch["sleep"], saida.getvalue(), codigo, ch


def sequencia(*itens):
    it = iter(itens)

    def g(url, **k):
        item = next(it)
        if isinstance(item, BaseException):
            raise item
        return item()
    return g


# ------------------------------------------------------------
# Métricas do pacote (lidas direto, independentes do serviço)
# ------------------------------------------------------------

def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def mae_rmse(cfg):
    m = (cfg or {}).get("metricas_teste") or {}
    return _num(m.get("mae")), _num(m.get("rmse"))


def modo_esperado(pac, alimentaveis):
    """MENOR MAE de teste (desempate: menor RMSE; depois ordem de prioridade)
    entre modelos COM lags alimentáveis; STARTUP só se não houver nenhum."""
    cands = []
    ordem = list(pac.get("ordem_prioridade") or ORDEM)
    for nome in alimentaveis:
        if nome == "STARTUP" or nome not in pac["modelos"]:
            continue
        mae, rmse = mae_rmse(pac["modelos"][nome])
        if mae is None:
            continue
        pos = ordem.index(nome) if nome in ordem else 99
        cands.append((mae, rmse if rmse is not None else float("inf"), pos, nome))
    if cands:
        return min(cands)[3]
    return "STARTUP" if "STARTUP" in pac["modelos"] else None


def copia_pacote(pac, remover=(), teste=None, cv=None, ordem=None):
    """Cópia em memória; o .pkl real nunca é tocado."""
    modelos = {}
    for nome, cfg in pac["modelos"].items():
        if nome in remover:
            continue
        novo = dict(cfg)
        if teste and nome in teste:
            novo["metricas_teste"] = teste[nome]
        if cv and nome in cv:
            novo["metricas_cv"] = cv[nome]
        modelos[nome] = novo
    novo_pac = {**pac, "modelos": modelos}
    if ordem is not None:
        novo_pac["ordem_prioridade"] = ordem
    return novo_pac


def prever(pac, offsets):
    return svc.prever_com_historico(pac, df_hist(offsets), checar_idade=False)


def checar_modo(pac, offsets, modo, lags, valores):
    r = prever(pac, offsets)
    cfg = pac["modelos"][r["prediction_mode"]]
    X = pd.DataFrame([[r["valores_features"][f] for f in cfg["features"]]],
                     columns=cfg["features"])
    previsao_ref = round(float(cfg["modelo"].predict(X)[0]), 2)
    erros = []
    if r["prediction_mode"] != modo:
        erros.append(f"modo={r['prediction_mode']} (esperado {modo})")
    if r["selecao"]["escolhido"] != modo:
        erros.append("selecao.escolhido difere do modo")
    if r["available_lags"] != lags:
        erros.append(f"available_lags={r['available_lags']} (esperado {lags})")
    if r["features_modelo"] != list(cfg["features"]):
        erros.append("features_modelo difere das features do modelo")
    if r["valores_features"] != valores:
        erros.append(f"features={r['valores_features']} (esperado {valores})")
    if not all(np.isfinite(v) for v in r["valores_features"].values()):
        erros.append("feature não finita")
    if r["previsao_60min_cm"] != previsao_ref:
        erros.append(f"previsão {r['previsao_60min_cm']} != predict() {previsao_ref}")
    det = (f"modo={r['prediction_mode']} lags={r['available_lags']} "
           f"+60min={r['previsao_60min_cm']}")
    return (not erros, "; ".join(erros) if erros else det)


# ------------------------------------------------------------
# Carga do pacote real
# ------------------------------------------------------------

print("=" * 70)
print("TESTES DO SERVIÇO V4 PROGRESSIVO  (SIMULADOS - NÃO validam o ESP32)")
print("=" * 70)

try:
    pacote = svc.carregar_modelo()
except Exception as erro:
    print(f"ERRO: não foi possível carregar o pacote real de modelos: {erro}")
    print("Execute na pasta codigo/ia, com o .pkl em "
          "codigo/floodsense_modelos_progressivos_60min_esp32.pkl.")
    sys.exit(2)
print(f"Modelos no pacote: {list(pacote['modelos'].keys())}\n")

E_3 = modo_esperado(pacote, ["LAG_5", "LAG_15"])
E_4 = modo_esperado(pacote, COM_LAGS)

M_LAG15 = {"LAG_5": {"mae": 12.0, "rmse": 15.0}, "LAG_15": {"mae": 8.0, "rmse": 11.0},
           "FULL": {"mae": 9.0, "rmse": 12.0}}
M_FULL = {"LAG_5": {"mae": 12.0, "rmse": 15.0}, "LAG_15": {"mae": 9.0, "rmse": 12.0},
          "FULL": {"mae": 8.0, "rmse": 11.0}}
M_LAG5 = {"LAG_5": {"mae": 8.0, "rmse": 11.0}, "LAG_15": {"mae": 9.0, "rmse": 12.0},
          "FULL": {"mae": 12.0, "rmse": 15.0}}

# ============================================================
print("--- TESTE 0: metadados do pacote atual vs. resumo do mesmo treinamento ---")
# ============================================================

for nome in ("STARTUP", "LAG_5", "LAG_15", "FULL"):
    def t0a(nome=nome):
        cfg = pacote["modelos"].get(nome)
        if cfg is None:
            return False, "modelo ausente do pacote"
        mae, rmse = mae_rmse(cfg)
        ok = mae is not None and rmse is not None and mae > 0 and rmse >= mae
        return ok, f"MAE={mae} RMSE={rmse} (finitos, MAE>0, RMSE>=MAE)"
    rodar(f"0a {nome}: métricas de teste válidas no pacote", t0a)


def t0b():
    if not RESUMO_CSV.exists():
        raise NaoExecutado(f"{RESUMO_CSV.name} não encontrado: pacote NÃO confrontado "
                           "com o resumo do treinamento")
    resumo = pd.read_csv(RESUMO_CSV).set_index("modelo_progressivo")
    erros = []
    treinados_csv = set(resumo.index[resumo["status"].astype(str) == "treinado"])
    if treinados_csv != set(pacote["modelos"]):
        erros.append(f"modelos treinados no CSV {sorted(treinados_csv)} != pacote "
                     f"{sorted(pacote['modelos'])}")
    for nome, cfg in pacote["modelos"].items():
        mae, rmse = mae_rmse(cfg)
        mae_csv = _num(resumo["mae_teste"].get(nome)) if nome in resumo.index else None
        rmse_csv = _num(resumo["rmse_teste"].get(nome)) if nome in resumo.index else None
        if mae is None or mae_csv is None or abs(mae - mae_csv) > 1e-6:
            erros.append(f"{nome}: MAE pacote={mae} CSV={mae_csv}")
        if rmse is None or rmse_csv is None or abs(rmse - rmse_csv) > 1e-6:
            erros.append(f"{nome}: RMSE pacote={rmse} CSV={rmse_csv}")
    return (not erros, "; ".join(erros) if erros else "MAE e RMSE do pacote == CSV")


rodar("0b pacote == resumo_modelos_progressivos.csv (MAE e RMSE, todos os modelos)", t0b)


def t0c():
    linhas = []
    for nome, ref in MAE_REFERENCIA_ANTIGA.items():
        mae, _ = mae_rmse(pacote["modelos"].get(nome))
        linhas.append(f"{nome}: atual={mae} | referência antiga={ref}")
    return True, " || ".join(linhas) + f" || vencedor c/ lags (4 leituras)={E_4}"


rodar("0c informativo: pacote atual vs. referência de treinamento antigo (não reprova)", t0c)


def t0d():
    erros = []
    if int(pacote.get("horizonte_minutos", -1)) != 60:
        erros.append(f"horizonte_minutos={pacote.get('horizonte_minutos')}")
    if pacote.get("sensor_id") != "FS-001":
        erros.append(f"sensor_id={pacote.get('sensor_id')}")
    return (not erros, "; ".join(erros) if erros else "horizonte 60 min e sensor FS-001")


rodar("0d pacote declara horizonte 60 min e sensor FS-001", t0d)
print()

# ============================================================
print("--- TESTE 1-5: seleção progressiva e disponibilidade de lags ---")
# ============================================================

rodar("1 - somente leitura atual -> STARTUP",
      lambda: checar_modo(pacote, [0], "STARTUP", [], VALORES_POR_MODO["STARTUP"]))
rodar("2 - atual + 5 min -> LAG_5",
      lambda: checar_modo(pacote, [5, 0], "LAG_5", ["5min"], VALORES_POR_MODO["LAG_5"]))
rodar(f"3 - atual + 5 + 15 min (pacote real; esperado pelas métricas: {E_3})",
      lambda: checar_modo(pacote, [15, 5, 0], E_3, LAGS_POR_MODO["LAG_15"],
                          VALORES_POR_MODO[E_3]))
rodar("3b - atual + 5 + 15 min, LAG_15 com menor MAE (métricas injetadas)",
      lambda: checar_modo(copia_pacote(pacote, teste=M_LAG15), [15, 5, 0], "LAG_15",
                          ["5min", "15min"], VALORES_POR_MODO["LAG_15"]))
rodar(f"4 - 4 leituras (pacote real; esperado pelas métricas: {E_4})",
      lambda: checar_modo(pacote, [30, 15, 5, 0], E_4, LAGS_POR_MODO["FULL"],
                          VALORES_POR_MODO[E_4]))
rodar("4b - 4 leituras, LAG_15 com menor MAE (injetado)",
      lambda: checar_modo(copia_pacote(pacote, teste=M_LAG15), [30, 15, 5, 0], "LAG_15",
                          LAGS_POR_MODO["FULL"], VALORES_POR_MODO["LAG_15"]))
rodar("4c - 4 leituras, FULL com menor MAE (injetado)",
      lambda: checar_modo(copia_pacote(pacote, teste=M_FULL), [30, 15, 5, 0], "FULL",
                          LAGS_POR_MODO["FULL"], VALORES_POR_MODO["FULL"]))
rodar("4d - 4 leituras, LAG_5 com menor MAE (injetado)",
      lambda: checar_modo(copia_pacote(pacote, teste=M_LAG5), [30, 15, 5, 0], "LAG_5",
                          LAGS_POR_MODO["FULL"], VALORES_POR_MODO["LAG_5"]))
rodar("5a - só 2 h e 3 h atrás (nenhum lag) -> STARTUP",
      lambda: checar_modo(pacote, [180, 120, 0], "STARTUP", [], VALORES_POR_MODO["STARTUP"]))
rodar("5b - tem 15 e 30, falta 5 -> STARTUP (LAG_15/FULL exigem o de 5)",
      lambda: checar_modo(pacote, [30, 15, 0], "STARTUP", ["15min", "30min"],
                          VALORES_POR_MODO["STARTUP"]))
rodar("5c - tem 5 e 30, falta 15 -> somente LAG_5 alimentável",
      lambda: checar_modo(pacote, [30, 5, 0], "LAG_5", ["5min", "30min"],
                          VALORES_POR_MODO["LAG_5"]))
rodar("5d - leituras a 9 e 11 min (fora de ±2 min) -> STARTUP",
      lambda: checar_modo(pacote, [11, 9, 0], "STARTUP", [], VALORES_POR_MODO["STARTUP"]))
rodar("5e - leitura a 7 min (limite aceito) -> LAG_5 com valor da leitura de 7 min",
      lambda: checar_modo(pacote, [7, 0], "LAG_5", ["5min"],
                          {"water_level": 200.0, "water_level_lag_1": 193.0}))
rodar("5f - leitura a 8 min (fora) -> STARTUP",
      lambda: checar_modo(pacote, [8, 0], "STARTUP", [], VALORES_POR_MODO["STARTUP"]))
rodar("5g - série densa antiga + gap de ~2 h + atual -> STARTUP",
      lambda: checar_modo(pacote, list(range(121, 200)) + [0], "STARTUP", [],
                          VALORES_POR_MODO["STARTUP"]))
rodar(f"5h - série densa de 40 min (esperado pelas métricas: {E_4})",
      lambda: checar_modo(pacote, list(range(40, -1, -1)), E_4, LAGS_POR_MODO["FULL"],
                          VALORES_POR_MODO[E_4]))


def t5i():
    """Fronteiras das tolerâncias (±2 min) nos DOIS lados, nos três lags."""
    casos = {  # offsets -> lags esperados
        (3, 0): ["5min"], (7, 0): ["5min"], (2, 0): [], (8, 0): [],
        (17, 0): ["15min"], (13, 0): ["15min"], (18, 0): [], (12, 0): [],
        (32, 0): ["30min"], (28, 0): ["30min"], (33, 0): [], (27, 0): [],
    }
    erros = []
    for offs, esperado in casos.items():
        _, lags, _ = svc.coletar_features_disponiveis(df_hist(list(offs)), pacote)
        if lags != esperado:
            erros.append(f"{offs}: {lags} != {esperado}")
    return (not erros, "; ".join(erros) if erros else "12 fronteiras corretas")


rodar("5i - tolerância ±2 min: aceita nas bordas, recusa fora (5, 15 e 30 min)", t5i)


def t5j():
    """Empate de distância (4 e 6 min): fica a leitura MAIS ANTIGA (como no treino)."""
    valores, _, _ = svc.coletar_features_disponiveis(df_hist([6, 4, 0]), pacote)
    return valores.get("water_level_lag_1") == 194.0, f"lag_1={valores.get('water_level_lag_1')} (esperado 194.0)"


rodar("5j - empate 4/6 min: usa a leitura mais antiga (6 min)", t5j)


def t5k():
    if not TREINO_PY.exists():
        raise NaoExecutado(f"{TREINO_PY.name} não encontrado para comparar")
    spec = importlib.util.spec_from_file_location("treino_v4", TREINO_PY)
    treino = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(treino)  # só define funções/constantes; treinar() não roda
    rng = np.random.default_rng(1)
    for _ in range(300):
        ts = np.sort(rng.choice(np.arange(0, 4000, 30), size=int(rng.integers(3, 40)),
                                replace=False))
        i = int(rng.integers(0, len(ts)))
        alvo = int(ts[i]) - int(rng.choice([300, 900, 1800]))
        for direcao in ("passado", "futuro"):
            a = svc.buscar_leitura_proxima(ts, alvo, 120, i, direcao)
            b = treino.buscar_leitura_proxima(ts, alvo, 120, i, direcao)
            if a != b:
                return False, f"divergência serviço={a} treino={b} (ts={ts.tolist()}, i={i})"
    return True, "300 casos aleatórios idênticos ao treinamento"


rodar("5k - busca de lag do serviço == busca de lag do treinamento", t5k)
print()

# ============================================================
print("--- TESTE 6-7: leitura antiga / futura / Firebase fora ---")
# ============================================================


def t6():
    try:
        svc.prever_com_historico(pacote, pd.DataFrame(
            [{"timestamp": int(time.time()) - 3 * 3600, "water_level": 100.0}]),
            checar_idade=True)
    except svc.LeituraAntigaError as e:
        return True, str(e)
    return False, "leitura de 3 h deveria ser recusada"


rodar("6 - leitura de 3 h atrás é recusada", t6)


def t6b():
    def idade(min_):
        return svc.prever_com_historico(pacote, pd.DataFrame(
            [{"timestamp": int(time.time() - min_ * 60), "water_level": 100.0}]),
            checar_idade=True)
    idade(14.0)  # aceita
    try:
        idade(16.0)
    except svc.LeituraAntigaError:
        return True, "14 min aceita; 16 min recusada"
    return False, "16 min deveria ser recusada"


rodar("6b - limite de idade: 14 min aceita, 16 min recusada", t6b)


def t6c():
    try:
        svc.prever_com_historico(pacote, pd.DataFrame(
            [{"timestamp": int(time.time()) + 600, "water_level": 42.0}]),
            checar_idade=True)
    except ValueError as e:
        return "futuro" in str(e).lower(), str(e)
    return False, "timestamp 10 min no futuro deveria ser recusado"


rodar("6c - timestamp 10 min no futuro é recusado", t6c)


def t6d():
    ret, ch, _ = rodar_ciclo(fb_hist([0], agora=time.time() + 600))
    return ret is None and not ch["patch"], f"retorno={ret is None} PATCHs={len(ch['patch'])}"


rodar("6d - leitura futura no ciclo: nada é publicado", t6d)


def t7():
    def get_falho(url, **k):
        raise requests.exceptions.ConnectionError("simulado: sem rede")
    with ambiente(get=get_falho) as ch:
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            ret = svc.ciclo_seguro()
    log = saida.getvalue()
    ok = ret is None and not ch["patch"] and "ConnectionError" in log
    return ok, f"retorno None={ret is None}; PATCHs={len(ch['patch'])}; log cita ConnectionError={'ConnectionError' in log}"


rodar("7 - Firebase fora (ConnectionError): ciclo devolve None, não publica, loga a causa", t7)
print()

# ============================================================
print("--- TESTE 8: JSON publicado (PATCH simulado) ---")
# ============================================================


def t8():
    agora = int(time.time())
    hist = fb_hist([30, 15, 5, 0], agora=agora)
    ret, ch, log = rodar_ciclo(hist)
    if ret is None or len(ch["patch"]) != 1:
        return False, f"ciclo não publicou exatamente 1 PATCH (patches={len(ch['patch'])}) log={log[-200:]}"
    url, p = ch["patch"][0]
    modo = modo_esperado(pacote, COM_LAGS)
    cfg = pacote["modelos"][modo]
    mae, _ = mae_rmse(cfg)
    X = pd.DataFrame([[VALORES_POR_MODO[modo][f] for f in cfg["features"]]], columns=cfg["features"])
    prev = round(float(cfg["modelo"].predict(X)[0]), 2)
    lim = 90 if prev >= 90 else (60 if prev >= 60 else 0)
    status_ref = {90: "critical", 60: "warning", 0: "normal"}[lim]
    classe = str(cfg.get("algoritmo_classe", "desconhecido")).replace("Regressor", "")
    gerado = datetime.fromisoformat(p["generated_at"]) if "generated_at" in p else None
    checks = {
        "rota PATCH literal": url == URL_PREVISAO,
        "campos do dashboard presentes": CAMPOS_DASHBOARD.issubset(p),
        "campos V4 presentes": CAMPOS_V4.issubset(p),
        "horizon_minutes == 60": p.get("horizon_minutes") == 60,
        "sensor_unit == cm": p.get("sensor_unit") == "cm",
        "sensor_id == FS-001": p.get("sensor_id") == "FS-001",
        "real_sensor_compatible True": p.get("real_sensor_compatible") is True,
        "current_level_cm == 200.0": p.get("current_level_cm") == 200.0,
        "reading_timestamp == leitura atual": p.get("reading_timestamp") == agora,
        f"prediction_mode == {modo} (menor MAE do pacote)": p.get("prediction_mode") == modo,
        "available_lags == 5/15/30": p.get("available_lags") == ["5min", "15min", "30min"],
        "predicted == predict() do modelo escolhido": p.get("predicted_level_60min_cm") == prev,
        "status pelos limites 60/90": p.get("status") == status_ref,
        "model_algorithm == pacote": p.get("model_algorithm") == cfg.get("algoritmo", "desconhecido"),
        "model_version == pacote": p.get("model_version") == cfg.get("versao_modelo", "desconhecida"),
        "model == classe do pacote": p.get("model") == classe,
        "selection_metric == mae_test": p.get("selection_metric") == "mae_test",
        "selection_mae_test_cm == MAE do pacote": mae is not None and p.get("selection_mae_test_cm") == mae,
        "initial_fallback False": p.get("initial_fallback") is False,
        "generated_at ISO com fuso": gerado is not None and gerado.tzinfo is not None,
    }
    falhos = [k for k, v in checks.items() if not v]
    return (not falhos, f"reprovados: {falhos}" if falhos else f"{len(checks)} campos/valores conferidos (modo {modo})")


rodar("8 - payload completo: rota, campos, valores, previsão e status", t8)


def t8b():
    ret, ch, log = rodar_ciclo(fb_hist([0]))
    if ret is None or not ch["patch"]:
        return False, "STARTUP não publicou"
    p = ch["patch"][0][1]
    ok = (p["prediction_mode"] == "STARTUP" and p["initial_fallback"] is True
          and p["selection_metric"] == "fallback_inicial" and p["available_lags"] == []
          and p["current_level_cm"] == 200.0 and "FALLBACK INICIAL" in log)
    return ok, f"modo={p['prediction_mode']} fallback={p['initial_fallback']} metric={p['selection_metric']}"


rodar("8b - STARTUP identificado como fallback inicial no payload e nos logs", t8b)
print()

# ============================================================
print("--- TESTE 9: limites de status (literais 60/90) ---")
# ============================================================


def t9():
    erros = []
    for nivel, esperado in [(0, "normal"), (59.99, "normal"), (60, "warning"),
                            (89.99, "warning"), (90, "critical"), (120, "critical")]:
        if svc.calcular_status(nivel) != esperado:
            erros.append(f"status({nivel})={svc.calcular_status(nivel)} esperado {esperado}")
    try:
        svc.calcular_status(float("nan"))
        erros.append("NaN deveria levantar ValueError")
    except ValueError:
        pass
    return (not erros, "; ".join(erros) if erros else "6 limites + NaN recusado")


rodar("9 - calcular_status nos limites 59.99/60/89.99/90 e NaN", t9)
print()

# ============================================================
print("--- TESTE 10: fonte do histórico e erros do Firebase ---")
# ============================================================


def t10():
    ret, ch, _ = rodar_ciclo(fb_hist([0]))
    ok = (ret is not None and ch["get"] == [URL_HISTORICO]
          and not any(URL_HISTORICO_PROIBIDO in u for u in ch["get"])
          and ret["historico_usado"] == "/sensor_history_treinamento/FS-001.json")
    return ok, f"GETs={ch['get']}"


rodar("10 - lê somente /sensor_history_treinamento/FS-001.json", t10)


def t10b():
    ret, ch, log = rodar_ciclo({})
    ok = (ret is None and ch["get"] == [URL_HISTORICO] and not ch["patch"]
          and "Nenhuma leitura" in log)
    return ok, f"retorno None={ret is None}; GETs={ch['get']}; PATCHs={len(ch['patch'])}"


rodar("10b - histórico vazio: erro claro, SEM fallback para /sensor_history", t10b)


def t10c():
    erros = []
    for codigo in (401, 403, 500):
        with ambiente(get=lambda u, **k: Resp(codigo, {"error": "x"})):
            try:
                svc.buscar_historico("/sensor_history_treinamento/FS-001.json")
                erros.append(f"HTTP {codigo} virou histórico vazio")
            except requests.exceptions.HTTPError:
                pass
        ret, ch, log = rodar_ciclo_http(codigo)
        if ret is not None or ch["patch"] or "Nenhuma leitura" in log or "ERRO" not in log:
            erros.append(f"HTTP {codigo} no ciclo: ret={ret is None} patches={len(ch['patch'])} log={log[:120]!r}")
    return (not erros, "; ".join(erros) if erros else "401/403/500 propagam erro e não publicam")


def rodar_ciclo_http(codigo):
    with ambiente(get=lambda u, **k: Resp(codigo, {"error": "x"})) as ch:
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            ret = svc.ciclo_seguro()
    return ret, ch, saida.getvalue()


rodar("10c - HTTP 401/403/500 na leitura: erro explícito (não vira 'histórico vazio')", t10c)


def t10d():
    agora = int(time.time())
    dados = {
        "abc": {"level": 50.0},                        # timestamp inválido
        str(agora - 600): {"level": None},             # nível nulo
        str(agora - 540): {"level": "x"},              # texto
        str(agora - 480): {"level": float("nan")},     # NaN
        str(agora - 420): {"level": float("inf")},     # infinito
        str(agora - 360): "não é dicionário",          # valor não-dict
        str(agora - 300): {"nolevel": 1.0},            # sem campo level
        str(agora - 120): {"level": 80.0},             # válida
        str(agora): {"level": 81.5},                   # válida
    }
    with ambiente(get=lambda u, **k: Resp(200, dados)):
        df = svc.buscar_historico("/sensor_history_treinamento/FS-001.json")
    esperado = [agora - 120, agora]
    ok = df["timestamp"].tolist() == esperado and df["water_level"].tolist() == [80.0, 81.5]
    erros = []
    for formato in ([1, 2, 3], "texto", 42):
        with ambiente(get=lambda u, f=formato, **k: Resp(200, f)):
            try:
                svc.buscar_historico("/x.json")
                erros.append(f"formato {type(formato).__name__} aceito")
            except ValueError:
                pass
    with ambiente(get=lambda u, **k: Resp(200, None)):
        vazio = svc.buscar_historico("/x.json").empty
    return (ok and not erros and vazio,
            f"timestamps={df['timestamp'].tolist()} erros={erros} null->vazio={vazio}")


rodar("10d - dados inválidos (null, texto, NaN, inf, não-dict, timestamp ruim) são descartados", t10d)


def t10e():
    dados = {str(AGORA): {"level": 70.0}, str(AGORA): {"level": 71.0}}
    with ambiente(get=lambda u, **k: Resp(200, dados)):
        df = svc.buscar_historico("/x.json")
    return len(df) == 1, f"linhas={len(df)}"


rodar("10e - timestamps duplicados não geram linhas duplicadas", t10e)
print()

# ============================================================
print("--- TESTE 11: regras de seleção (cópias em memória do pacote) ---")
# ============================================================

rodar("11a - LAG_15 ausente do pacote -> FULL (menor MAE entre os restantes)",
      lambda: checar_modo(copia_pacote(pacote, remover=("LAG_15",),
                                       teste={"LAG_5": {"mae": 12.0, "rmse": 15.0},
                                              "FULL": {"mae": 8.0, "rmse": 11.0}}),
                          [30, 15, 5, 0], "FULL", LAGS_POR_MODO["FULL"], VALORES_POR_MODO["FULL"]))
rodar("11b - só LAG_5 no pacote -> LAG_5",
      lambda: checar_modo(copia_pacote(pacote, remover=("LAG_15", "FULL")),
                          [30, 15, 5, 0], "LAG_5", LAGS_POR_MODO["FULL"], VALORES_POR_MODO["LAG_5"]))
rodar("11c - LAG_15 com MAE NaN não vence FULL com MAE válido",
      lambda: checar_modo(copia_pacote(pacote, teste={
          "LAG_5": {"mae": 12.0, "rmse": 15.0}, "LAG_15": {"mae": float("nan")},
          "FULL": {"mae": 8.0, "rmse": 11.0}}),
          [30, 15, 5, 0], "FULL", LAGS_POR_MODO["FULL"], VALORES_POR_MODO["FULL"]))
rodar("11d - empate de MAE: menor RMSE vence (FULL)",
      lambda: checar_modo(copia_pacote(pacote, teste={
          "LAG_5": {"mae": 20.0, "rmse": 25.0}, "LAG_15": {"mae": 8.0, "rmse": 12.0},
          "FULL": {"mae": 8.0, "rmse": 11.0}}),
          [30, 15, 5, 0], "FULL", LAGS_POR_MODO["FULL"], VALORES_POR_MODO["FULL"]))
rodar("11e - STARTUP com MAE menor NÃO vence modelo com lags",
      lambda: checar_modo(copia_pacote(pacote, teste={"STARTUP": {"mae": 1.0, "rmse": 1.0}}),
                          [5, 0], "LAG_5", ["5min"], VALORES_POR_MODO["LAG_5"]))
rodar("11f - critério é MAE (não RMSE): LAG_5 tem MAE menor e RMSE maior -> LAG_5",
      lambda: checar_modo(copia_pacote(pacote, teste={
          "LAG_5": {"mae": 8.0, "rmse": 30.0}, "LAG_15": {"mae": 9.0, "rmse": 10.0},
          "FULL": {"mae": 12.0, "rmse": 12.0}}),
          [30, 15, 5, 0], "LAG_5", LAGS_POR_MODO["FULL"], VALORES_POR_MODO["LAG_5"]))
rodar("11g - critério é métrica de TESTE (não CV): CV favorável ao FULL é ignorada",
      lambda: checar_modo(copia_pacote(pacote, teste=M_LAG15,
                                       cv={"FULL": {"mae": 0.5, "rmse": 0.5}}),
                          [30, 15, 5, 0], "LAG_15", LAGS_POR_MODO["FULL"], VALORES_POR_MODO["LAG_15"]))
rodar("11h - empate total (MAE e RMSE): ordem de prioridade do pacote (FULL)",
      lambda: checar_modo(copia_pacote(pacote, ordem=ORDEM, teste={
          "LAG_5": {"mae": 9.0, "rmse": 11.0}, "LAG_15": {"mae": 8.0, "rmse": 11.0},
          "FULL": {"mae": 8.0, "rmse": 11.0}}),
          [30, 15, 5, 0], "FULL", LAGS_POR_MODO["FULL"], VALORES_POR_MODO["FULL"]))


def t11i():
    """Modelos com lags alimentáveis, mas nenhum com MAE válido: não publicar."""
    pac = copia_pacote(pacote, teste={n: {"mae": float("nan")} for n in COM_LAGS})
    try:
        prever(pac, [30, 15, 5, 0])
    except RuntimeError as e:
        pass
    else:
        return False, "deveria levantar RuntimeError (sem MAE válido)"
    r = prever(pac, [0])  # só STARTUP alimentável: segue normalmente
    return r["prediction_mode"] == "STARTUP", f"STARTUP segue funcionando: modo={r['prediction_mode']}"


rodar("11i - sem MAE válido nos modelos com lags: recusa escolher; STARTUP continua", t11i)
print()

# ============================================================
print("--- TESTE 12: falha de publicação, leitura velha/nova, pacote ---")
# ============================================================


def t12():
    def patch_falha(url, json=None, **k):
        raise requests.exceptions.HTTPError("simulado: 500")
    ret, ch, log = rodar_ciclo(fb_hist([30, 15, 5, 0]), patch=patch_falha)
    ok = ret is None and len(ch["patch"]) == 1 and "ERRO" in log and "HTTPError" in log
    return ok, f"retorno None={ret is None}; tentativas PATCH={len(ch['patch'])}; log={log[-120:]!r}"


rodar("12 - falha ao PUBLICAR (HTTP 500): ciclo devolve None e loga o erro", t12)


def t12b():
    r1, ch1, log1 = rodar_ciclo(fb_hist([0], agora=time.time() - 16.2 * 60))
    r2, ch2, log2 = rodar_ciclo(fb_hist([0], agora=time.time() - 30))
    ok = (r1 is None and not ch1["patch"] and "AVISO" in log1 and "16." in log1
          and r2 is not None and len(ch2["patch"]) == 1)
    return ok, f"16.2 min: publicou={bool(ch1['patch'])}; 0.5 min: publicou={bool(ch2['patch'])}"


rodar("12b - leitura de 16.2 min: AVISO e nada publicado; leitura nova volta a publicar", t12b)


def t12c():
    with tempfile.TemporaryDirectory() as tmp:
        ruim = copy.copy(pacote)
        ruim["horizonte_minutos"] = 30
        caminho = Path(tmp) / "pacote_horizonte_30.pkl"
        joblib.dump(ruim, caminho)
        antigo = (svc.MODEL_PATH, dict(svc._CACHE_MODELO))
        svc.MODEL_PATH = caminho
        svc._CACHE_MODELO.update(mtime=None, pacote=None)
        try:
            svc.carregar_modelo()
        except RuntimeError as e:
            return "Horizonte" in str(e) or "horizonte" in str(e), str(e)
        finally:
            svc.MODEL_PATH = antigo[0]
            svc._CACHE_MODELO.clear()
            svc._CACHE_MODELO.update(antigo[1])
    return False, "pacote com horizonte 30 min deveria ser recusado"


rodar("12c - pacote com horizonte != 60 é recusado (arquivo temporário; .pkl real intocado)", t12c)
print()

# ============================================================
print("--- TESTE 13: serviço contínuo, --once e Ctrl+C (relógio de espera simulado) ---")
# ============================================================


def get_ok(url, **k):
    return Resp(200, fb_hist([30, 15, 5, 0]))


def t13a():
    sleeps, out, codigo, ch = rodar_main([], get_ok, max_sleeps=3)
    ok = (codigo == 0 and sleeps == [300, 300, 300] and len(ch["get"]) == 3
          and len(ch["patch"]) == 3 and "Ctrl+C" in out and "Traceback" not in out)
    return ok, f"saída={codigo} esperas={sleeps} GETs={len(ch['get'])} PATCHs={len(ch['patch'])}"


rodar("13a - contínuo: 3 ciclos, espera de 300 s entre eles, Ctrl+C encerra com código 0 sem traceback", t13a)


def t13b():
    sleeps, out, codigo, ch = rodar_main(["--intervalo", "2"], get_ok, max_sleeps=2)
    return codigo == 0 and sleeps == [2, 2] and len(ch["get"]) == 2, f"esperas={sleeps} saída={codigo}"


rodar("13b - --intervalo 2: espera pedida = 2 s, 2 ciclos", t13b)


def t13c():
    sleeps, out, codigo, ch = rodar_main(["--once"], get_ok)
    return codigo == 0 and sleeps == [] and len(ch["get"]) == 1 and len(ch["patch"]) == 1, \
        f"saída={codigo} esperas={sleeps} PATCHs={len(ch['patch'])}"


rodar("13c - --once com sucesso: 1 ciclo, 1 publicação, sem espera, código 0", t13c)


def t13d():
    def get_falho(url, **k):
        raise requests.exceptions.ConnectionError("simulado")
    sleeps, out, codigo, ch = rodar_main(["--once"], get_falho)
    return codigo == 1 and sleeps == [] and not ch["patch"], f"saída={codigo} esperas={sleeps}"


rodar("13d - --once com falha: não publica e sai com código 1", t13d)


def t13e():
    seq = sequencia(requests.exceptions.ConnectionError("simulado: DNS"),
                    lambda: Resp(200, fb_hist([30, 15, 5, 0])),
                    requests.exceptions.Timeout("simulado: timeout"),
                    lambda: Resp(200, fb_hist([30, 15, 5, 0])))
    sleeps, out, codigo, ch = rodar_main([], seq, max_sleeps=4)
    ok = (codigo == 0 and len(sleeps) == 4 and len(ch["patch"]) == 2
          and out.count("ERRO neste ciclo") == 2 and "Traceback" not in out)
    return ok, f"ciclos={len(sleeps)} publicações={len(ch['patch'])} erros logados={out.count('ERRO neste ciclo')}"


rodar("13e - ConnectionError e Timeout intercalados: serviço segue; publica nos ciclos bons", t13e)


def t13f():
    def patch_falha(url, json=None, **k):
        raise requests.exceptions.HTTPError("simulado: 500")
    sleeps, out, codigo, ch = rodar_main([], get_ok, patch=patch_falha, max_sleeps=2)
    return (codigo == 0 and len(sleeps) == 2 and len(ch["patch"]) == 2
            and out.count("ERRO neste ciclo") == 2), f"esperas={sleeps} tentativas PATCH={len(ch['patch'])}"


rodar("13f - falha ao publicar em todos os ciclos: serviço continua e loga cada erro", t13f)


def t13g():
    def get_ctrl_c(url, **k):
        raise KeyboardInterrupt
    sleeps, out, codigo, ch = rodar_main([], get_ctrl_c)
    return codigo == 0 and sleeps == [] and "Ctrl+C" in out and "Traceback" not in out, \
        f"saída={codigo} esperas={sleeps}"


rodar("13g - Ctrl+C NO MEIO de um ciclo: encerra com código 0 sem traceback", t13g)


def t13h():
    return svc.INTERVALO_CICLO_SEGUNDOS == 300 and svc.MAX_IDADE_LEITURA_MIN == 15, \
        f"intervalo={svc.INTERVALO_CICLO_SEGUNDOS}s limite idade={svc.MAX_IDADE_LEITURA_MIN} min"


rodar("13h - intervalo normal de 5 min (300 s) e limite de idade de 15 min preservados", t13h)

# ============================================================
# RESUMO
# ============================================================
n_ok = sum(1 for r in RESULTADOS if r[0] == "PASSOU")
n_fail = sum(1 for r in RESULTADOS if r[0] == "FALHOU")
n_skip = sum(1 for r in RESULTADOS if r[0] == "NAO EXECUTADO")

print("\n" + "=" * 70)
print("RESUMO - TESTES SIMULADOS (Firebase e relógio substituídos)")
print("=" * 70)
print(f"Total: {len(RESULTADOS)} | Aprovados: {n_ok} | Falhos: {n_fail} | Não executados: {n_skip}")
for status, nome, det in RESULTADOS:
    if status != "PASSOU":
        print(f"  {status}: {nome}\n      {det}")

print("\nVALIDAÇÃO COM O ESP32 FÍSICO: NÃO EXECUTADA POR ESTE SCRIPT (checklist manual):")
for item in (
    "ESP32 + AJ-SR04M gravando leituras reais em /sensor_history_treinamento/FS-001.json",
    "intervalo real entre leituras compatível com os lags de 5/15/30 min (±2 min)",
    "serviço publicando em /ai_predictions/FS-001 com o Firebase REAL e regras de acesso",
    "dashboard exibindo a previsão real (inclusive sem o campo available_lags no STARTUP)",
    "queda e retorno reais de energia/Wi-Fi do ESP32 (serviço retomando sozinho)",
):
    print(f"  [ ] {item}")

print("=" * 70)
if n_fail:
    print("RESULTADO GERAL: HÁ FALHAS")
    code = 1
elif n_skip:
    print("RESULTADO GERAL: SEM FALHAS, MAS INCOMPLETO (há testes não executados)")
    code = 2
else:
    print("RESULTADO GERAL: TODOS OS TESTES SIMULADOS PASSARAM (ESP32 físico não validado)")
    code = 0
print("=" * 70)
sys.exit(code)