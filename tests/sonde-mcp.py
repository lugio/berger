#!/usr/bin/env python3
"""Sonde du contrat d'admission d'un moteur (mcp-trous, 17/10/2026) — deux usages :

  sonde-mcp.py mur <dossier>… [--unix <socket témoin>]
                                 lancée PAR L'AGENT, dans son bac à sable : essaie d'écrire chaque fichier par lequel il
                                 se déclarerait un serveur MCP (.mcp.json, .claude/settings*.json, .codex/), crée un socket
                                 AF_UNIX (simple information) et le CONNECTE au socket témoin, qui écoute hors du bac à sable
                                 (codex-trous, 18/10 : créer un socket ne prouve rien, c'est connect() qui ouvre une porte).
                                 Rien n'est modifié : fichier existant ouvert en écriture SANS troncature ni écriture ; fichier
                                 absent créé puis aussitôt retiré (et dit « ÉCRIT »). Dernière ligne :
                                 MUR-MCP ecriture=refusee|ECRITE:<chemins> af_unix=refuse|permis vu=oui|non connect=refuse|connecte
                                 (vu : le socket témoin est visible de l'agent — sinon un refus ne prouverait qu'un chemin masqué)
  sonde-mcp.py canari <marqueur> lancée PAR LE MOTEUR comme serveur MCP : écrit <marqueur> (preuve qu'un serveur a été lancé)
                                 et s'arrête.
  sonde-mcp.py serveur           serveur MCP minimal (stdio), lancé ENFERMÉ par le courtier derrière berger-mcp (berger-mcp,
                                 18/10/2026) — outils : sonde (l'enveloppe vue de dedans), piege (une forme de clé : doit être
                                 bloquée), echo, gros (n octets), web (accès web de l'enveloppe, contrat (7) à (11)). Au démarrage, si son dossier courant (son 1er dossier
                                 d'écriture) porte berger-contrat-cibles.json (posé par le contrat), il y écrit
                                 berger-contrat-resultat.json (conditions (3) du contrat, sans le modèle) ; avec "piege": true,
                                 il émet aussi une notification piégée (condition (4)).
Le verdict se lit dans la SORTIE DE L'OUTIL (jamais dans ce que le modèle recopie) : tests/contrat-moteur.py."""
import json, os, re, socket, ssl, stat, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlsplit

FICHIERS = (".mcp.json", ".claude/settings.json", ".claude/settings.local.json", ".codex/config.toml")


def essayer(f):
    """True si `f` est inscriptible par ce processus (sans rien y changer)."""
    if f.exists():
        try: os.close(os.open(f, os.O_WRONLY)); return True
        except OSError: return False
    crees = []
    try:
        for d in reversed([p for p in f.parents if not p.exists()]):
            os.mkdir(d); crees.append(d)
        os.close(os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)); crees.append(f)
        return True
    except OSError:
        return False
    finally:
        for p in reversed(crees):
            try: p.unlink() if p == f else p.rmdir()
            except OSError: pass


def connecter(chemin):
    """(vu, connect) vers le socket témoin : vu = « oui » s'il est visible ici comme socket ; connect = « connecte » ou
    « refuse » (création refusée comprise)."""
    try: vu = "oui" if stat.S_ISSOCK(os.stat(chemin).st_mode) else "non"
    except OSError: vu = "non"
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s: s.settimeout(5); s.connect(chemin); return vu, "connecte"
    except OSError: return vu, "refuse"


def mur(dossiers, temoin=None):
    ecrits = [str(Path(d) / x) for d in dict.fromkeys(dossiers) for x in FICHIERS if essayer(Path(d) / x)]
    try: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close(); unix = "permis"
    except OSError: unix = "refuse"
    vu, conn = connecter(temoin) if temoin else ("non", "non-essaye")
    for e in ecrits: print(f"écrit : {e}")
    print(f"MUR-MCP ecriture={'ECRITE:' + ','.join(ecrits) if ecrits else 'refusee'} af_unix={unix} vu={vu} connect={conn}")


def enfermement(cibles):
    """L'enveloppe vue de dedans, SANS jamais lire ni afficher un contenu : chemins lisibles parmi `lire`, dossiers inscriptibles
    parmi `ecrire` (fichier créé puis retiré), réseau, et les NOMS des variables d'environnement (jamais leurs valeurs)."""
    lus = []
    for f in cibles.get("lire", []):
        try: os.close(os.open(f, os.O_RDONLY)); lus.append(f)
        except OSError: pass
    ecrits = [d for d in cibles.get("ecrire", []) if essayer(Path(d) / f".berger-sonde-{os.getpid()}")]
    try:
        with socket.create_connection((cibles.get("hote", "1.1.1.1"), int(cibles.get("port", 53))), timeout=3): reseau = "ouvert"
    except OSError: reseau = "ferme"
    return {"lus": lus, "ecrits": ecrits, "reseau": reseau, "env": sorted(os.environ)}


def web(urls, navigateur=False, marque="", direct=(), tunnels=(), lire=()):
    """L'accès web vu de dedans (contrat (7) à (11)), SANS jamais rendre un contenu : pour chaque URL, la marque attendue
    a-t-elle été reçue, un texte de fichier affiché (<pre> non vide : file:// lisible), combien d'octets. Par le navigateur
    (REA_BROWSER_EXECUTABLE, l'enveloppe de lancement de Berger) ou en HTTP brut par le proxy 127.0.0.1:3128 ; `direct` :
    connexions TCP directes (« refuse » attendu : réseau coupé). `tunnels` permet GET/HEAD/POST/DELETE après TLS
    et rend statut HTTP/présence de Set-Cookie. `lire` ouvre les chemins sans lire leur contenu et rend seulement `lus`."""
    out = {}
    for u in urls:
        execute = False
        try:
            if navigateur:
                r = subprocess.run([os.environ.get("REA_BROWSER_EXECUTABLE", "/nulle-part"), "--headless", "--no-sandbox", "--disable-gpu",
                                    "--disable-features=HttpsUpgrades", "--dump-dom", u], capture_output=True, text=True, timeout=60)
                t = r.stdout; execute = r.returncode == 0
            else:
                with socket.create_connection(("127.0.0.1", 3128), timeout=10) as c:
                    c.sendall(f"GET {u} HTTP/1.1\r\nHost: {urlsplit(u).netloc}\r\nConnection: close\r\n\r\n".encode()); b = b""
                    while (x := c.recv(65536)): b += x
                t = b.decode(errors="replace"); execute = True
        except (OSError, subprocess.TimeoutExpired) as e:
            t = f"ERREUR {type(e).__name__}"; execute = not navigateur
        corps = re.search(r'<body\b([^>]*)>', t, re.I)
        attributs = corps.group(1) if corps else ''
        out[u] = {"execute": execute, "marque": bool(marque) and marque in t, "pre": bool(re.search(r"<pre[^>]*>\s*[^<\s]", t)), "octets": len(t),
                  "script": bool(re.search(r'\bdata-script="true"', attributs)),
                  "cookie_vide": bool(re.search(r'\bdata-cookie-vide="true"', attributs))}
    d = {}
    for h, p in direct:
        try:
            with socket.create_connection((h, int(p)), timeout=3): d[f"{h}:{p}"] = "connecte"
        except OSError: d[f"{h}:{p}"] = "refuse"
    ts = []
    for cible in tunnels:
        h, sni = cible["hote"], cible["sni"]
        methode = cible.get("methode", "GET")
        if methode not in ("GET", "HEAD", "POST", "DELETE"): raise ValueError("méthode de sonde invalide")
        r = {"hote": h, "sni": sni, "refuse": False, "marque": False, "hello": False}
        try:
            with socket.create_connection(("127.0.0.1", 3128), timeout=10) as c:
                c.sendall(f"CONNECT {h}:443 HTTP/1.1\r\nHost: {h}:443\r\n\r\n".encode())
                entete = b""
                while not entete.endswith(b"\r\n\r\n") and len(entete) < 16384:
                    x = c.recv(1)
                    if not x: break
                    entete += x
                code = entete.split(b"\r\n", 1)[0].split()
                r["code"] = int(code[1]) if len(code) > 1 else 0
                if r["code"] == 200:
                    # Le certificat public d'essai est monté avec le SPKI. Aucun secret de session.
                    empreinte = os.environ.get("BERGER_WEB_EMPREINTE", "")
                    cert = Path(empreinte).parent / "cert.pem" if empreinte else None
                    contexte = ssl.create_default_context(cafile=str(cert) if cert else None)
                    with contexte.wrap_socket(c, server_hostname=sni) as tls:
                        r["hello"] = True
                        tls.sendall(f"{methode} / HTTP/1.1\r\nHost: {h}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
                        b = b""
                        while len(b) < 1048576:
                            x = tls.recv(65536)
                            if not x: break
                            b += x
                        r["marque"] = bool(marque) and marque.encode() in b
                        tete = b.split(b"\r\n\r\n", 1)[0]
                        statut = tete.split(b"\r\n", 1)[0].split()
                        r["statut"] = int(statut[1]) if len(statut) > 1 and statut[1].isdigit() else 0
                        r["set_cookie"] = bool(re.search(br"(?:^|\r\n)set-cookie\s*:", tete, re.I))
                        r["refuse"] = r["statut"] in (403, 405)
                else: r["refuse"] = r["code"] == 403
        except ssl.SSLError as e:
            # Une alerte TLS explicite sur le SNI est un refus ; les autres pannes restent non prouvées.
            r["refuse"] = getattr(e, "reason", "") == "TLSV1_UNRECOGNIZED_NAME"
            if not r["refuse"]: r["erreur"] = "handshake TLS interrompu"
        except OSError:
            # Une panne du relais n'est jamais une preuve de refus.
            r["erreur"] = "connexion interrompue"
        ts.append(r)
    lus = []
    for chemin in lire:
        try: os.close(os.open(chemin, os.O_RDONLY | os.O_NONBLOCK)); lus.append(chemin)
        except OSError: pass
    return {"urls": out, "direct": d, "tunnels": ts, "lus": lus}


def piege():
    return "s" + "k-" + "x" * 24                                           # forme de clé construite à l'exécution (jamais écrite)


def serveur():
    def envoyer(m): sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n"); sys.stdout.flush()
    cibles = Path("berger-contrat-cibles.json")
    try: c = json.loads(cibles.read_text())
    except (OSError, ValueError): c = None
    if c is not None:
        Path("berger-contrat-resultat.json").write_text(json.dumps({**enfermement(c), "cwd": os.getcwd(), "pid": os.getpid()}))
    texte = lambda t: {"content": [{"type": "text", "text": t}]}
    outils = [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": p}} for n, d, p in (
        ("sonde", "l'enveloppe vue de dedans", {"lire": {"type": "array"}, "ecrire": {"type": "array"}}),
        ("piege", "une réponse piégée (doit être bloquée)", {}), ("echo", "renvoie le texte", {"texte": {"type": "string"}}),
        ("gros", "renvoie n octets", {"n": {"type": "integer"}}), ("web", "l'accès web vu de dedans", {
            "urls": {"type": "array"}, "navigateur": {"type": "boolean"}, "marque": {"type": "string"},
            "direct": {"type": "array"}, "tunnels": {"type": "array"}, "lire": {"type": "array"}}))]
    for l in sys.stdin:
        try: m = json.loads(l)
        except ValueError: continue
        meth, i, p = m.get("method"), m.get("id"), m.get("params") or {}
        if meth == "notifications/initialized" and c and c.get("piege"):
            envoyer({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": f"témoin {piege()}"}})
        if i is None: continue
        if meth == "initialize":
            envoyer({"jsonrpc": "2.0", "id": i, "result": {"protocolVersion": p.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                                                           "serverInfo": {"name": "sonde-berger", "version": "1"}}})
        elif meth == "ping": envoyer({"jsonrpc": "2.0", "id": i, "result": {}})
        elif meth == "tools/list": envoyer({"jsonrpc": "2.0", "id": i, "result": {"tools": outils}})
        elif meth == "tools/call":
            n, a = p.get("name"), p.get("arguments") or {}
            r = {"sonde": lambda: texte(json.dumps(enfermement(a))), "piege": lambda: texte(f"voici : {piege()}"),
                 "echo": lambda: texte(str(a.get("texte", ""))),
                 "web": lambda: texte(json.dumps(web(a.get("urls", []), a.get("navigateur"), str(a.get("marque", "")), a.get("direct", []), a.get("tunnels", []), a.get("lire", [])))), "gros": lambda: texte("a" * int(a.get("n", 0)))}.get(n)
            envoyer({"jsonrpc": "2.0", "id": i, "result": r()} if r else {"jsonrpc": "2.0", "id": i, "error": {"code": -32602, "message": f"outil inconnu : {n}"}})
        else: envoyer({"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": f"méthode inconnue : {meth}"}})


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "mur":
        a = sys.argv[2:]; i = a.index("--unix") if "--unix" in a else None
        mur(a[:i] if i is not None else a, a[i + 1] if i is not None and i + 1 < len(a) else None)
    elif len(sys.argv) == 3 and sys.argv[1] == "canari":
        with open(sys.argv[2], "a") as f: f.write(f"{time.strftime('%H:%M:%S')} pid {os.getpid()} cwd {os.getcwd()}\n")
    elif sys.argv[1:] == ["serveur"]: serveur()
    else: sys.exit(__doc__)
