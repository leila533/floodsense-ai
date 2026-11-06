import json, statistics, time, urllib.parse, urllib.request
from email.utils import parsedate_to_datetime

DB = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
HIST = "/sensor_history_treinamento/FS-001"
N_AMOSTRAS = 5
INTERVALO_S = 0.5
ARQ_SEGREDOS = r"codigo\ia\segredos.env"


def ler_segredos(caminho):
    cfg = {}
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def get(url, espera=15):
    """Devolve (dado, hora_do_servidor_em_epoch)."""
    try:
        r = urllib.request.urlopen(url, timeout=espera)
        srv = parsedate_to_datetime(r.headers["Date"]).timestamp()
        return json.load(r), srv
    except Exception:
        return None, None


def main():
    cfg = ler_segredos(ARQ_SEGREDOS)
    req = urllib.request.Request(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + cfg["FS_API_KEY"],
        data=json.dumps({"email": cfg["FS_DEVICE_EMAIL"], "password": cfg["FS_DEVICE_PASSWORD"],
                         "returnSecureToken": True}).encode(),
        headers={"Content-Type": "application/json"})
    token = json.load(urllib.request.urlopen(req, timeout=30))["idToken"]

    q = urllib.parse.urlencode({"auth": token, "orderBy": '"$key"', "limitToLast": 1})
    url = f"{DB}{HIST}.json?{q}"

    def mais_novo():
        d, srv = get(url)
        if not d:
            return None, None, None
        k = max(d, key=lambda x: int(x))
        return int(k), d[k], srv

    ultimo, _, srv = mais_novo()
    if ultimo is None:
        print("Não consegui ler o histórico. Confira rede e login.")
        return
    print(f"Relógio do PC menos relógio do servidor: {time.time() - srv:+.1f} s")
    print("Registro mais recente agora:", ultimo, "(há", round(srv - ultimo), "s pela hora do servidor)")
    print(f"Esperando {N_AMOSTRAS} registros novos (cerca de {N_AMOSTRAS} min). Não aperte Ctrl+C.")

    atrasos = []
    limite = time.time() + 600
    while len(atrasos) < N_AMOSTRAS and time.time() < limite:
        k, dado, srv = mais_novo()
        if k is not None and k != ultimo:
            ts = dado.get("timestamp", k) if isinstance(dado, dict) else k
            a = srv - ts
            atrasos.append(a)
            print(f"  registro {k}: atraso {a:5.1f} s (hora do servidor)")
            ultimo = k
        time.sleep(INTERVALO_S)

    if not atrasos:
        print("Nenhum registro novo em 10 min.")
        return
    atrasos.sort()
    print("\nAmostras:", len(atrasos))
    print(f"Mediana: {statistics.median(atrasos):.1f} s")
    print(f"Média:   {statistics.mean(atrasos):.1f} s")
    print(f"Máximo:  {atrasos[-1]:.1f} s")
    print(f"Mínimo:  {atrasos[0]:.1f} s")


main()