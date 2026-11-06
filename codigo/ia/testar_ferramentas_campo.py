import contextlib
import io
import sys
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import avaliar_previsoes_campo as ava  # noqa: E402
import monitorar_previsoes_campo as mon  # noqa: E402

# ============================================================
# Testes SIMULADOS das ferramentas de validação em campo.
# Não acessam a rede real (qualquer tentativa reprova) nem o projeto:
# gravam só em pastas temporárias.
#   cd codigo\ia && python testar_ferramentas_campo.py
# ============================================================

RESULTADOS = []


def rodar(nome, fn):
    try:
        r = fn()
        ok, det = r if isinstance(r, tuple) else (bool(r), "")
    except Exception as e:  # noqa: BLE001
        ok, det = False, f"{type(e).__name__}: {e} | {traceback.format_exc().splitlines()[-3].strip()}"
    RESULTADOS.append(ok)
    print(f"{'PASSOU' if ok else 'FALHOU'} | {nome}" + (f"\n      {det}" if det else ""))


class Resp:
    def __init__(self, status=200, dados=None):
        self.status_code, self._d = status, dados

    def json(self):
        return self._d

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} simulado")


@contextlib.contextmanager
def sem_rede(get):
    bloqueios = []
    original = (requests.get, requests.adapters.HTTPAdapter.send)

    def envio_real(self, request, **k):
        bloqueios.append(request.url)
        raise AssertionError(f"REDE REAL BLOQUEADA: {request.url}")

    requests.get = get
    requests.adapters.HTTPAdapter.send = envio_real
    try:
        yield
    finally:
        requests.get, requests.adapters.HTTPAdapter.send = original
    if bloqueios:
        raise AssertionError(f"tentativa de rede real: {bloqueios}")


T0 = 1_800_000_000


def hist_minuto_a_minuto(minutos=240, base=100.0, passo=0.1):
    ts = np.array([T0 + 60 * m for m in range(minutos)], dtype=np.int64)
    return ts, base + passo * np.arange(minutos)


def log_df(linhas):
    return pd.DataFrame(linhas, columns=[
        "reading_timestamp", "current_level_cm", "predicted_level_60min_cm", "prediction_mode"])


print("=" * 70)
print("TESTES DAS FERRAMENTAS DE CAMPO (SIMULADOS - não validam o ESP32)")
print("=" * 70)


def t_avaliacao_basica():
    ts, niveis = hist_minuto_a_minuto()
    # leitura em T0 (nível 100.0); real em +60 min = 106.0; previsão 106.2 -> erro 0.2; baseline 6.0
    pares = ava.parear(log_df([(T0, 100.0, 106.2, "LAG_5")]), ts, niveis)
    m = ava.calcular_metricas(pares)
    todos = m[m["modo"] == "TODOS"].iloc[0]
    ok = (pares.loc[0, "estado"] == "pareado" and abs(pares.loc[0, "real_level_60min_cm"] - 106.0) < 1e-9
          and abs(todos["mae_modelo_cm"] - 0.2) < 1e-6 and abs(todos["mae_baseline_cm"] - 6.0) < 1e-6
          and abs(todos["melhoria_mae_pct"] - (6.0 - 0.2) / 6.0 * 100) < 0.01)
    return ok, f"mae={todos['mae_modelo_cm']} baseline={todos['mae_baseline_cm']} melhoria={todos['melhoria_mae_pct']}%"


rodar("1 - par previsão x real: erro do modelo, baseline e melhoria", t_avaliacao_basica)


def t_pendente_e_sem_leitura():
    ts, niveis = hist_minuto_a_minuto(minutos=100)       # histórico vai até T0+99 min
    # a) alvo T0+60 min existe; b) previsão de T0+50 min -> alvo T0+110 min: ainda não aconteceu
    pend = ava.parear(log_df([(T0 + 50 * 60, 105.0, 110.0, "FULL")]), ts, niveis)
    # c) histórico com buraco: some tudo entre +50 e +70 min, mas existe leitura depois
    ts2 = np.array([t for t in hist_minuto_a_minuto()[0] if not (T0 + 50 * 60 <= t <= T0 + 70 * 60)])
    nv2 = np.linspace(100, 124, len(ts2))
    sem = ava.parear(log_df([(T0, 100.0, 106.0, "FULL")]), ts2, nv2)
    return (pend.loc[0, "estado"] == "pendente" and sem.loc[0, "estado"] == "sem_leitura",
            f"pendente={pend.loc[0, 'estado']} sem_leitura={sem.loc[0, 'estado']}")


rodar("2 - alvo ainda não ocorreu = pendente; buraco no histórico = sem_leitura", t_pendente_e_sem_leitura)


def t_tolerancia():
    base_ts = np.array([T0, T0 + 3600 + 120], dtype=np.int64)       # exatamente na borda (+2 min)
    fora_ts = np.array([T0, T0 + 3600 + 121, T0 + 3600 + 300], dtype=np.int64)
    a = ava.parear(log_df([(T0, 100.0, 106.0, "X")]), base_ts, np.array([100.0, 106.0]))
    b = ava.parear(log_df([(T0, 100.0, 106.0, "X")]), fora_ts, np.array([100.0, 106.0, 107.0]))
    return (a.loc[0, "estado"] == "pareado" and b.loc[0, "estado"] == "sem_leitura",
            f"borda 120 s={a.loc[0, 'estado']} | 121 s={b.loc[0, 'estado']}")


rodar("3 - tolerância ±2 min: aceita 120 s, recusa 121 s", t_tolerancia)


def t_mais_proxima():
    ts = np.array([T0, T0 + 3600 - 90, T0 + 3600 + 30, T0 + 3600 + 200], dtype=np.int64)
    nv = np.array([100.0, 105.0, 106.0, 107.0])
    p = ava.parear(log_df([(T0, 100.0, 106.0, "X")]), ts, nv)
    return p.loc[0, "real_level_60min_cm"] == 106.0, f"real={p.loc[0, 'real_level_60min_cm']} (esperado 106.0: a mais próxima)"


rodar("4 - usa a leitura real MAIS PRÓXIMA do alvo", t_mais_proxima)


def t_status():
    ts, niveis = hist_minuto_a_minuto(base=55.0, passo=0.1)   # real em +60 min = 61.0 (warning)
    pares = ava.parear(log_df([(T0, 55.0, 59.0, "X")]), ts, niveis)  # prevê 59 (normal): subestimou
    m = ava.calcular_metricas(pares).iloc[-1]
    ok = m["alertas_subestimados"] == 1 and m["alertas_superestimados"] == 0 and m["status_acertos_pct"] == 0.0
    return ok, f"subestimados={m['alertas_subestimados']} acertos={m['status_acertos_pct']}%"


rodar("5 - alerta subestimado (previu normal, real warning) é contado", t_status)


def t_limites_status():
    casos = [(59.99, "normal"), (60, "warning"), (89.99, "warning"), (90, "critical")]
    erros = [f"{n}->{ava.status_de(n)}" for n, e in casos if ava.status_de(n) != e]
    return not erros, "; ".join(erros) if erros else "limites 60/90 corretos"


rodar("6 - limites de status 59.99/60/89.99/90", t_limites_status)


def t_por_modo():
    ts, niveis = hist_minuto_a_minuto()
    d = log_df([(T0, 100.0, 106.0, "LAG_5"), (T0 + 60, 100.1, 106.1, "FULL"), (T0 + 120, 100.2, 107.2, "FULL")])
    m = ava.calcular_metricas(ava.parear(d, ts, niveis))
    n = dict(zip(m["modo"], m["pares"]))
    return n == {"LAG_5": 1, "FULL": 2, "TODOS": 3}, f"pares por modo={n}"


rodar("7 - métricas separadas por modo de previsão + total", t_por_modo)


def t_sem_pares():
    ts, niveis = hist_minuto_a_minuto(minutos=30)
    pares = ava.parear(log_df([(T0, 100.0, 106.0, "X")]), ts, niveis)
    return ava.calcular_metricas(pares).empty and ava.contagens(pares)["pendente"] == 1, "sem pares -> métricas vazias"


rodar("8 - sem nenhum par: não inventa métrica", t_sem_pares)


def t_cli_offline_e_erros():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ts, niveis = hist_minuto_a_minuto()
        pd.DataFrame({"timestamp": ts, "water_level": niveis}).to_csv(tmp / "hist.csv", index=False)
        log_df([(T0, 100.0, 106.2, "LAG_5")]).assign(
            reading_timestamp=lambda d: d.reading_timestamp).to_csv(tmp / "log.csv", index=False)
        saida = io.StringIO()
        with sem_rede(lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria usar GET"))):
            with contextlib.redirect_stdout(saida):
                c_ok = ava.main(["--log", str(tmp / "log.csv"), "--historico-csv", str(tmp / "hist.csv"),
                                 "--saida", str(tmp / "pares.csv")])
                c_sem = ava.main(["--log", str(tmp / "nao_existe.csv"), "--saida", str(tmp / "p2.csv")])
        texto = saida.getvalue()
        ok = (c_ok == 0 and c_sem == 1 and (tmp / "pares.csv").exists()
              and "TODOS" in texto and "somente" not in texto.lower().replace("somente leitura", ""))
        return ok, f"saídas={c_ok},{c_sem}"


rodar("9 - CLI offline (--historico-csv) funciona; log ausente -> código 1; sem rede", t_cli_offline_e_erros)


def previsao(ts_leitura, **extra):
    p = {"reading_timestamp": ts_leitura, "current_level_cm": 70.0, "predicted_level_60min_cm": 72.5,
         "status": "warning", "prediction_mode": "FULL", "available_lags": ["5min", "15min", "30min"],
         "model_algorithm": "RF", "model_version": "v4_progressivo", "selection_metric": "mae_test",
         "selection_mae_test_cm": 17.57, "initial_fallback": False, "sensor_id": "FS-001",
         "horizon_minutes": 60, "generated_at": "2026-10-23T12:00:00+00:00"}
    p.update(extra)
    return p


def t_monitor_registro_e_duplicado():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "log.csv"
        r = [mon.registrar(previsao(T0), caminho), mon.registrar(previsao(T0), caminho),
             mon.registrar(previsao(T0 + 300), caminho)]
        df = pd.read_csv(caminho)
        ok = (r == ["novo", "duplicado", "novo"] and len(df) == 2 and list(df.columns) == mon.COLUNAS
              and df.loc[0, "available_lags"] == "5min;15min;30min")
        return ok, f"retornos={r} linhas={len(df)}"


rodar("10 - monitor: registra, ignora duplicado, cabeçalho único", t_monitor_registro_e_duplicado)


def t_monitor_invalidos():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "log.csv"
        ruins = [previsao(None), previsao(T0, current_level_cm=float("nan")),
                 previsao(T0, predicted_level_60min_cm="x"), previsao(T0, sensor_id="FS-002"),
                 previsao(T0, horizon_minutes=30)]
        r = [mon.registrar(p, caminho) for p in ruins]
        return all(x.startswith("invalido") for x in r) and not caminho.exists(), f"retornos={[x[:28] for x in r]}"


rodar("11 - monitor: previsão inválida/outro sensor/horizonte errado não é registrada", t_monitor_invalidos)


def t_monitor_startup_sem_lags():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "log.csv"
        p = previsao(T0, prediction_mode="STARTUP", initial_fallback=True)
        del p["available_lags"]          # o Firebase descarta array vazio
        r = mon.registrar(p, caminho)
        df = pd.read_csv(caminho)
        return r == "novo" and pd.isna(df.loc[0, "available_lags"]), f"retorno={r}"


rodar("12 - monitor: STARTUP sem o campo available_lags é registrado", t_monitor_startup_sem_lags)


def t_monitor_erros_http():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "log.csv"

        def ciclo_com(get):
            saida = io.StringIO()
            with sem_rede(get):
                with contextlib.redirect_stdout(saida):
                    r = mon.ciclo(caminho)
            return r, saida.getvalue()

        def conexao_caida(url, **k):
            raise requests.exceptions.ConnectionError("x")

        casos = {
            "HTTP 401": (lambda url, **k: Resp(401, {}), "[ERRO]"),
            "HTTP 500": (lambda url, **k: Resp(500, {}), "[ERRO]"),
            "formato ruim": (lambda url, **k: Resp(200, [1, 2]), "[ERRO]"),
            "rede fora": (conexao_caida, "[ERRO]"),
            "nó vazio": (lambda url, **k: Resp(200, None), "Nenhuma previsão"),
        }
        erros = []
        for nome, (get, esperado) in casos.items():
            r, log = ciclo_com(get)
            if r is not None or esperado not in log:
                erros.append(f"{nome}: retorno={r} log={log[:60]!r}")
            if nome != "nó vazio" and "Nenhuma previsão" in log:
                erros.append(f"{nome}: erro virou 'nó vazio'")
        if caminho.exists():
            erros.append("gravou arquivo mesmo com erro")
        return not erros, "; ".join(erros) if erros else "5 cenários: erro explícito, sem gravar, sem derrubar"


rodar("13 - monitor: 401/500/formato ruim/rede fora = erro explícito; nó vazio = aviso; nada é gravado", t_monitor_erros_http)


def t_monitor_loop_e_ctrl_c():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "log.csv"
        esperas = []

        def sleep_(s):
            esperas.append(s)
            if len(esperas) >= 3:
                raise KeyboardInterrupt

        original = time.sleep
        time.sleep = sleep_
        saida = io.StringIO()
        try:
            seq = iter([previsao(T0), previsao(T0), previsao(T0 + 300)])
            with sem_rede(lambda url, **k: Resp(200, next(seq))):
                with contextlib.redirect_stdout(saida):
                    codigo = mon.main(["--log", str(caminho)])
        finally:
            time.sleep = original
        df = pd.read_csv(caminho)
        ok = codigo == 0 and esperas == [60, 60, 60] and len(df) == 2 and "Traceback" not in saida.getvalue()
        return ok, f"saída={codigo} esperas={esperas} linhas={len(df)}"


rodar("14 - monitor contínuo: 3 ciclos a cada 60 s, Ctrl+C encerra limpo (código 0)", t_monitor_loop_e_ctrl_c)


def t_monitor_once():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "log.csv"
        with sem_rede(lambda url, **k: Resp(200, previsao(T0))):
            with contextlib.redirect_stdout(io.StringIO()):
                c_ok = mon.main(["--once", "--log", str(caminho)])
        with sem_rede(lambda url, **k: Resp(500, {})):
            with contextlib.redirect_stdout(io.StringIO()):
                c_falha = mon.main(["--once", "--log", str(Path(tmp) / "outro.csv")])
        return c_ok == 0 and c_falha == 1, f"sucesso={c_ok} falha={c_falha}"


rodar("15 - monitor --once: código 0 com sucesso, 1 com falha", t_monitor_once)


def t_somente_leitura():
    fontes = [Path(mon.__file__).read_text(encoding="utf-8"), Path(ava.__file__).read_text(encoding="utf-8")]
    return not any("requests.patch" in f or "requests.put" in f or "requests.post" in f
                   or "requests.delete" in f for f in fontes), "nenhuma escrita no Firebase no código"


rodar("16 - as duas ferramentas só fazem GET (nenhum patch/put/post/delete)", t_somente_leitura)

n_ok = sum(RESULTADOS)
print("\n" + "=" * 70)
print(f"Total: {len(RESULTADOS)} | Aprovados: {n_ok} | Falhos: {len(RESULTADOS) - n_ok}")
print("RESULTADO GERAL:", "TODOS OS TESTES SIMULADOS PASSARAM" if n_ok == len(RESULTADOS) else "HÁ FALHAS")
print("Estes testes não validam o ESP32 nem o Firebase reais.")
print("=" * 70)
sys.exit(0 if n_ok == len(RESULTADOS) else 1)