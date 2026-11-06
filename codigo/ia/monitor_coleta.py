import json, time, urllib.error, urllib.parse, urllib.request
from email.utils import parsedate_to_datetime

# Usa o repositório de certificados do Windows (a verificação continua ligada).
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

MODO_TESTE = True       # True = teste do aviso (limite 30 s). Trocar para False no uso normal.

DB = "https://floodsense-ai-7a6b9-default-rtdb.firebaseio.com"
HIST = "/sensor_history_treinamento/FS-001"
ARQ_SEGREDOS = r"codigo\ia\segredos.env"
ARQ_LOG = r"codigo\ia\monitor_coleta.log"
LIMITE_S = 30 if MODO_TESTE else 600        # avisa se o último registro for mais velho que isso
CHECAR_A_CADA_S = 20 if MODO_TESTE else 60
RENOVAR_LOGIN_S = 45 * 60


def ler_segredos(caminho):
    cfg = {}
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                k, v = linha.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    return cfg


def log(msg):
    linha = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + msg
    print(linha)
    with open(ARQ_LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def telegram(cfg, texto):
    try:
        dados = urllib.parse.urlencode({"chat_id": cfg["TELEGRAM_CHAT_ID"], "text": texto}).encode()
        url = f"https://api.telegram.org/bot{cfg['TELEGRAM_TOKEN']}/sendMessage"
        urllib.request.urlopen(urllib.request.Request(url, data=dados), timeout=15).read()
        return True
    except urllib.error.HTTPError as e:
        log(f"Telegram recusou: HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        log(f"Telegram sem conexão: {e.reason}")
    except KeyError as e:
        log(f"Falta a variável {e} no segredos.env")
    except Exception as e:
        log(f"Falha ao enviar Telegram: {type(e).__name__}: {e}")
    return False


def login(cfg):
    req = urllib.request.Request(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + cfg["FS_API_KEY"],
        data=json.dumps({"email": cfg["FS_DEVICE_EMAIL"], "password": cfg["FS_DEVICE_PASSWORD"],
                         "returnSecureToken": True}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=30))["idToken"]


def idade_ultimo_registro(token):
    """Devolve a idade (s) do registro mais recente, pela hora do servidor."""
    q = urllib.parse.urlencode({"auth": token, "orderBy": '"$key"', "limitToLast": 1})
    r = urllib.request.urlopen(f"{DB}{HIST}.json?{q}", timeout=20)
    srv = parsedate_to_datetime(r.headers["Date"]).timestamp()
    d = json.load(r)
    if not d:
        return None
    return srv - max(int(k) for k in d)


def main():
    cfg = ler_segredos(ARQ_SEGREDOS)
    token, t_login = None, 0
    parado = False
    inicio_parada = None

    modo = "TESTE (limite 30 s)" if MODO_TESTE else "normal (limite 10 min)"
    log(f"Monitor iniciado, modo {modo}.")
    telegram(cfg, f"FloodSense: monitor de coleta iniciado, modo {modo}.")

    while True:
        try:
            if token is None or time.time() - t_login > RENOVAR_LOGIN_S:
                token = login(cfg)
                t_login = time.time()
            idade = idade_ultimo_registro(token)
        except Exception as e:
            log(f"Não consegui consultar o Firebase ({type(e).__name__}). Sem conclusão sobre o sensor.")
            token = None
            time.sleep(CHECAR_A_CADA_S)
            continue

        if idade is None:
            log("Histórico vazio.")
        elif idade > LIMITE_S:
            log(f"SEM LEITURA há {idade/60:.1f} min.")
            if not parado:
                parado = True
                inicio_parada = time.time() - idade
                telegram(cfg, f"FloodSense: sem leitura nova há {idade/60:.0f} min. Confira o ESP32, a energia e o Wi-Fi.")
        else:
            log(f"OK, último registro há {idade:.0f} s.")
            if parado:
                parado = False
                dur = (time.time() - inicio_parada) / 60
                telegram(cfg, f"FloodSense: coleta voltou. Ficou cerca de {dur:.1f} min sem leitura.")
        time.sleep(CHECAR_A_CADA_S)


main()