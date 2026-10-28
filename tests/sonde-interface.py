#!/usr/bin/env python3
"""Sonde « un agent ne joint pas l'interface web » (spec docs/plans/2026-10-13-interface-spec.md, §5 et §6 ter) — lancée DANS
le bac à sable d'un agent par tests/tout.sh, qui a démarré hors bac à sable un serveur d'essai sur l'adresse DÉCLARÉE
([interface] adresse, défaut 127.0.0.1) et un port libre. Pour 127.0.0.1 ET l'adresse déclarée (lot 1c : l'adresse de la VM),
vert seulement si : connexion directe refusée OU réponse 401/403 sans jeton ; par le mandataire réseau du bac à sable (s'il y
en a un) : refus OU 401/403 ; le jeton du propriétaire et la clé du certificat interne sont illisibles. Toute réponse 200 est
rouge. N'affiche jamais de contenu. Usage : python3 sonde-interface.py <port> [<adresse déclarée>]"""
import http.client, os, sys, urllib.request
from pathlib import Path

port = int(sys.argv[1]); ko = 0
adresses = list(dict.fromkeys([".".join(("127", "0", "0", "1"))] + sys.argv[2:3]))   # boucle locale, puis l'adresse déclarée


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def direct(adr):
    try:
        c = http.client.HTTPConnection(adr, port, timeout=5); c.request("GET", "/api/vues", headers={"Host": f"localhost:{port}"})
        return c.getresponse().status
    except (OSError, http.client.HTTPException) as e: return f"refusé ({type(e).__name__})"


def par_mandataire(adr):
    proxies = urllib.request.getproxies()
    if not proxies.get("http"): return "aucun mandataire"
    try: return urllib.request.build_opener(urllib.request.ProxyHandler(proxies)).open(f"http://{adr}:{port}/api/vues", timeout=8).status
    except urllib.error.HTTPError as e: return e.code
    except (OSError, http.client.HTTPException) as e: return f"refusé ({type(e).__name__})"


for adr in adresses:
    r = direct(adr); dire(r in (401, 403) or isinstance(r, str), f"connexion directe à {adr}:{port} → {r} (refus, 401 ou 403 attendus)")
    r = par_mandataire(adr); dire(r in (401, 403) or isinstance(r, str), f"{adr}:{port} par le mandataire du bac à sable → {r} (refus, 401 ou 403 attendus)")
config = Path.home() / ".config" / "berger"
for nom, f in (("jeton d'entrée", config / "interface.jeton"), ("clé du certificat interne", config / "interface" / "cle.pem")):
    try: lu = bool(f.read_bytes().strip())
    except OSError: lu = False
    dire(not lu, f"{nom} du propriétaire : illisible depuis le bac à sable")
print(f"---- {ko} échec(s)")
