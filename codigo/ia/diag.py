import json, time, urllib.request

DB = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"


def ler_segredos(caminho):
    cfg = {}
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


cfg = ler_segredos(r"codigo\ia\segredos.env")
req = urllib.request.Request(
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + cfg["FS_API_KEY"],
    data=json.dumps({"email": cfg["FS_DEVICE_EMAIL"], "password": cfg["FS_DEVICE_PASSWORD"],
                     "returnSecureToken": True}).encode(),
    headers={"Content-Type": "application/json"})
token = json.load(urllib.request.urlopen(req, timeout=15))["idToken"]

url = f'{DB}/sensor_history_treinamento.json?auth={token}&orderBy="$key"&limitToLast=3'
dado = json.load(urllib.request.urlopen(url, timeout=15))
print(time.strftime("%H:%M:%S"), json.dumps(dado, ensure_ascii=False, indent=1))