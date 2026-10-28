#!/usr/bin/env python3
"""Tests de berger-mcp (18/10/2026, docs/plans/2026-10-18-berger-mcp-spec.md) — sans modèle, installation JETABLE :
GÉNÉRATION — seulement des `berger-mcp <agent> <serveur>` dans les configs (Claude : .mcp-berger.json par --mcp-config, suivi
de --strict-mcp-config ; Codex : mcp_servers du profil, approuvé pour CE serveur), rien pour un agent sans `mcp =`, le fichier
et le dossier des sockets protégés ;
REFUS (§ 3) — serveur non déclaré ou hors du `mcp =`, mur ouvert, développeur d'équipe, commande qui télécharge ou
introuvable, écriture hors du dossier ou sur un fichier protégé, env de secret, bwrap absent ou en échec, proposition ;
RELAIS (courtier/_mcp.py) — le protocole passe tel quel ; journal (une ligne par appel, sans valeur) ; filtre (valeur d'un
coffre d'essai, forme de clé, notification) ; débit et taille ; ENVELOPPE exécutée avec la sonde : coffre, autre agent,
config, réseau, écriture hors et dans `ecriture`, environnement vidé ;
WEB (voie B, fusion 2/3) — serveur déclaré `web = true` et agent qui a le droit `web` : dossier du socket monté en lecture
seule, socat 127.0.0.1:3128, REA_BROWSER_EXECUTABLE = bin/berger-navigateur-web (--proxy-server imposé) ; refus (réseau,
navigateur introuvable ou masqué) ; sans le droit : enveloppe ordinaire ; enveloppe réelle : sans accès rien ne sort, un accès
ouvert APRÈS le lancement est vu sans relance (NON JOUÉ sans AF_UNIX) ;
SOCKET — relais bin/berger-mcp ↔ vrai courtier (NON JOUÉ là où AF_UNIX est refusé, ex. dans un bac à sable Claude).
Usage : python3 tests/mcp.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, json, os, runpy, shutil, socket, ssl, subprocess, sys, tempfile, time, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0
# Serveur MCP minimal écrit EN LIGNE (aucun fichier) : il tourne dans l'enveloppe réelle, même quand l'installation jetable est
# sous /tmp (remplacé par le temporaire de l'agent) — celui du vrai courtier, dans la partie socket.
MINIMAL = ("import json, sys\nfor l in sys.stdin:\n    m = json.loads(l)\n    if 'id' in m: "
           "print(json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': {'methode': m['method']}}), flush=True)")


# Faux Chromium (tests seulement) : suit --proxy-server comme Chromium (la boucle locale aussi avec <-loopback>), sans moteur de
# rendu ; 1re ligne : {"argv": …} ; sortie : le corps reçu. BERGER_FAUX_SEC : n'ouvre rien, n'écrit que la ligne argv.
FAUX_NAVIGATEUR = r'''import json, os, socket, sys
from urllib.parse import urlsplit
a = sys.argv[1:]; print(json.dumps({"argv": a}), flush=True)
if os.environ.get("BERGER_FAUX_SEC"): sys.exit(0)
url = [x for x in a if not x.startswith("--")][-1]; u = urlsplit(url)
prx = next((x.split("=", 1)[1] for x in a if x.startswith("--proxy-server=")), None)
boucle = u.hostname in ("127.0.0.1", "localhost") and "--proxy-bypass-list=<-loopback>" not in a
try:
    if u.scheme == "file": print(open(u.path, errors="replace").read())
    else:
        p = urlsplit(prx) if prx and not boucle else u
        s = socket.create_connection((p.hostname, p.port or 80), timeout=10)
        s.sendall(f"GET {url if prx and not boucle else u.path or '/'} HTTP/1.1\r\nHost: {u.hostname}\r\n\r\n".encode()); b = b""
        while (x := s.recv(65536)): b += x
        print(b.decode(errors="replace"))
except OSError as e: print(f"ERREUR {type(e).__name__}")
'''


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


def charger(nom, f):
    s = importlib.util.spec_from_file_location(nom, f); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def repondre_site(c, tls):
    """Même faux amont pour HTTP et HTTPS : termine réellement TLS avant de lire le GET."""
    try:
        c.settimeout(5)
        if c.recv(1, socket.MSG_PEEK) == b"\x16": c = tls.wrap_socket(c, server_side=True)
        c.recv(65536)
        c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 18\r\nConnection: close\r\n\r\nBERGER-SITE-PERMIS")
    finally: c.close()


with tempfile.TemporaryDirectory() as t:
    m = Path(t); i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (i / "tests").mkdir(); shutil.copy2(SRC / "tests/sonde-mcp.py", i / "tests/sonde-mcp.py")
    temoin = "Temoin" + "Coffre" + "Essai"                     # valeur secrète du coffre d'essai, construite à l'exécution
    (m / "coffre").mkdir(); coffre = m / "coffre/coffre-essai.json"; coffre.write_text(json.dumps({"service": {"jeton": temoin}}))
    py = os.path.realpath(sys.executable); sonde = [py, str(i / "tests/sonde-mcp.py"), "serveur"]
    nav = i / "tests/faux-navigateur"; nav.write_text(f"#!{py}\n" + FAUX_NAVIGATEUR); nav.chmod(0o755)
    nav_masque = m / "coffre/chrome"; shutil.copy2(nav, nav_masque)              # un navigateur dans un dossier masqué : refusé
    decl = lambda nom, **k: f"\n[mcp.{nom}]\n" + "".join(f"{x} = {json.dumps(v) if not isinstance(v, dict) else '{ ' + ', '.join(f'{a} = {json.dumps(b)}' for a, b in v.items()) + ' }'}\n" for x, v in k.items())
    (i / "config.toml").write_text(
        f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{coffre}"\n\n[equipes.proj]\ndepot = "{m}/depot"\n'
        + decl("sonde", commande=sonde, ecriture=["{agent}/echantillons"])
        + decl("borne", commande=sonde, max_par_minute=3, max_reponse="1K")
        + decl("ouvert-net", commande=sonde, reseau=True) + decl("minimal", commande=[py, "-c", MINIMAL])
        + decl("npx", commande=["npx", "-y", "serveur-quelconque"]) + decl("pipxrun", commande=["pipx", "run", "serveur"])
        + decl("introuvable", commande=[str(m / "absent/serveur")])
        + decl("hors", commande=sonde, ecriture=["{agent}/../beta"]) + decl("ailleurs", commande=sonde, ecriture=[str(m)])
        + decl("protege", commande=sonde, ecriture=["{agent}/agent.conf"]) + decl("boite", commande=sonde, ecriture=["{agent}/courrier"])
        + decl("envnom", commande=sonde, env={"API_TOKEN": "valeur"}) + decl("envcoffre", commande=sonde, env={"CHEMIN": temoin})
        + decl("sondeweb", commande=sonde, ecriture=["{agent}/echantillons"], web=True, navigateur=str(nav))
        + decl("webnet", commande=sonde, web=True, reseau=True, navigateur=str(nav))
        + decl("webnav", commande=sonde, web=True, navigateur=str(m / "absent/chrome"))
        + decl("webmasque", commande=sonde, web=True, navigateur=str(nav_masque)) + decl("webmal", commande=sonde, web="oui"))
    agents = {"delta": ("claude", "mcp = minimal"), "alpha": ("claude", "mcp = sonde, borne, ouvert-net"), "beta": ("codex", "mcp = sonde"), "gamma": ("claude", ""),
              "ouvert": ("claude", "mcp = sonde\nmur = ouvert"), "dev": ("claude", "mcp = sonde\nprojet = proj\nsujet = essai"),
              "refus": ("claude", "mcp = npx, pipxrun, introuvable, hors, ailleurs, protege, boite, envnom, envcoffre, absent"),
              "retro": ("claude", "mcp = sondeweb, webnet, webnav, webmasque, webmal\noutils = web"), "sansweb": ("claude", "mcp = sondeweb, webnet")}
    for a, (mo, plus) in agents.items():
        d = i / "agents" / a; (d / "memory").mkdir(parents=True)
        (d / "agent.conf").write_text(f"nom = {a}\nmoteur = {mo}\npanneaux = {mo}\nheures = aucune\n" + ("" if "outils =" in plus else "outils =\n") + f"{plus}\n")
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": "/bin/false", "BERGER_NOTIFY_SEND": "/bin/true",
           "BERGER_TMP_AGENTS": str(Path(tempfile.mkdtemp(prefix="bt", dir="/tmp")) if os.access("/tmp", os.W_OK) else m / "bt")}
    berger = lambda *a: subprocess.run([py, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=120)
    r = berger("regenerer")
    dire(r.returncode == 0, "regenerer réussit" + ("" if r.returncode == 0 else f" — {(r.stdout + r.stderr).strip()[-300:]}"))

    # ── GÉNÉRATION ──
    os.environ.update({k: env[k] for k in ("HOME", "BERGER_DIR", "BERGER_HERDR", "BERGER_TMP_AGENTS")})
    sys.argv = ["berger"]; g = runpy.run_path(str(i / "bin/berger"), run_name="essai")["lancer"].__globals__
    relais = str(i / "bin/berger-mcp")
    f = i / "agents/alpha/.mcp-berger.json"
    c = json.loads(f.read_text()) if f.is_file() else {}
    dire(c == {"mcpServers": {s: {"command": relais, "args": ["alpha", s]} for s in ("sonde", "borne", "ouvert-net")}},
         "Claude : .mcp-berger.json ne contient que « berger-mcp <agent> <serveur> » (ni vraie commande, ni chemin d'outil, ni variable)")
    args = g["moteurs"].MODULES["claude"].args("alpha")
    k = args.index("--mcp-config") if "--mcp-config" in args else -1
    dire(k >= 0 and args[k + 1] == str(f) and args[k + 2] == "--strict-mcp-config",
         "Claude : --mcp-config <dossier>/.mcp-berger.json suivi d'une option (--strict-mcp-config gardé)")
    for a in ("gamma", "ouvert", "dev"):
        dire(not (i / "agents" / a / ".mcp-berger.json").exists() and "--mcp-config" not in g["moteurs"].MODULES["claude"].args(a),
             f"{a} ({'sans mcp =' if a == 'gamma' else 'mur ouvert' if a == 'ouvert' else 'développeur'}) : ni fichier ni --mcp-config")
    p = tomllib.loads((i / ".codex/beta.config.toml").read_text()).get("mcp_servers", {})
    dire(p == {"sonde": {"command": relais, "args": ["beta", "sonde"], "default_tools_approval_mode": "approve"}},
         "Codex : mcp_servers du profil = berger-mcp seul, approuvé d'avance pour CE serveur (default_tools_approval_mode)")
    dire(all("mcp_servers" not in tomllib.loads((i / ".codex" / f"{a}.config.toml").read_text()) for a in ("gamma", "ouvert", "dev", "refus")),
         "Codex : aucun mcp_servers pour un agent sans serveur valide (sans mcp =, mur ouvert, développeur, tous refusés)")
    s = json.loads((i / "agents/alpha/.claude/settings.json").read_text())
    dire(str(f) in s["sandbox"]["filesystem"]["denyWrite"] and f"Edit(~/berger/agents/alpha/.mcp-berger.json)" in s["permissions"]["deny"]
         and f'"{f}" = "read"' in (i / ".codex/config.toml").read_text(), ".mcp-berger.json non inscriptible par l'agent (Claude et Codex)")
    dire("Read(~/berger/courtier/mcp/**)" in s["permissions"]["deny"] and f'"{i / "courtier/mcp"}" = "none"' in (i / ".codex/config.toml").read_text(),
         "dossier des sockets (courtier/mcp) masqué aux agents (Claude et Codex)")
    for x in ("npx", "pipxrun", "introuvable", "hors", "ailleurs", "protege", "boite", "envnom", "envcoffre", "absent"):
        dire(f"⚠ refus : mcp — " in r.stdout and f"[mcp.{x}]" in r.stdout or (x == "absent" and "« absent » non déclaré" in r.stdout),
             f"regenerer dit le refus de « {x} »")
    dire("⚠ ouvert : mcp — " in r.stdout and "⚠ dev : mcp — " in r.stdout, "regenerer dit le refus du mur ouvert et du développeur")

    # ── REFUS : berger mcp-enveloppe (la seule source, appelée par le courtier) ──
    for a, srv, mot in (("alpha", "inconnu", "non déclaré"), ("gamma", "sonde", "n'est pas dans"), ("ouvert", "sonde", "mur ouvert"),
                        ("dev", "sonde", "développeur"), ("refus", "npx", "télécharge"), ("refus", "pipxrun", "télécharge"),
                        ("refus", "introuvable", "introuvable"), ("refus", "hors", "hors du dossier"), ("refus", "ailleurs", "hors du dossier"),
                        ("refus", "protege", "protégé"), ("refus", "boite", "protégé"), ("refus", "envnom", "jamais un secret"),
                        ("refus", "envcoffre", "jamais un secret")):
        r = berger("mcp-enveloppe", a, srv)
        dire(r.returncode != 0 and mot in r.stderr and temoin not in r.stdout + r.stderr, f"refus : {a} / {srv} ({mot})")
    r = berger("mcp-enveloppe", "alpha", "sonde"); e = json.loads(r.stdout) if r.returncode == 0 else {}
    dire(e.get("commande") == sonde and e.get("ecriture") == [str(i / "agents/alpha/echantillons")] and e.get("reseau") is False
         and set(e.get("env", {})) == {"PATH", "HOME", "TMPDIR", "LANG"} and e.get("max_par_minute") == 30 and e.get("max_reponse") == 2 * 1024 * 1024,
         "enveloppe de alpha/sonde : commande résolue, écriture sous son dossier, sans réseau, env minimal, bornes par défaut")
    # ── WEB : génération de l'enveloppe (bin/berger, serveur_mcp) ──
    r = berger("mcp-enveloppe", "retro", "sondeweb"); e = json.loads(r.stdout) if r.returncode == 0 else {}
    w = e.get("web") or {}; dw = i / "courtier/mcp/retro-web"
    dire(w.get("dossier") == str(dw) and w.get("socket") == str(dw / "proxy.sock") and w.get("port") == 3128 and e.get("reseau") is False,
         f"web : dossier courtier/mcp/retro-web, socket proxy.sock, port 3128, réseau coupé ({r.stderr.strip()[-200:]})")
    dire(e.get("commande", [""])[:2] == ["/bin/sh", "-c"] and "TCP-LISTEN:3128,bind=127.0.0.1,fork" in e["commande"][2]
         and "UNIX-CONNECT:" in e["commande"][2] and e["commande"][3:5] == [str(dw / "proxy.sock"), shutil.which("socat") or "?"]
         and e["commande"][5:] == sonde, "web : socat 127.0.0.1:3128 → socket du proxy, puis le serveur (exec, même argv)")
    dire(e.get("env", {}).get("REA_BROWSER_EXECUTABLE") == str(i / "bin/berger-navigateur-web") and e["env"].get("BERGER_NAVIGATEUR") == str(nav),
         "web : REA_BROWSER_EXECUTABLE = l'enveloppe de lancement de Berger, BERGER_NAVIGATEUR = le Chromium déclaré")
    dire(str(i / "courtier/mcp") in e.get("masques", []), "web : courtier/mcp reste masqué (seul son dossier web est remonté)")
    r = berger("mcp-enveloppe", "sansweb", "sondeweb"); e2 = json.loads(r.stdout) if r.returncode == 0 else {}
    dire(r.returncode == 0 and e2.get("web") is None and e2.get("commande") == sonde and "REA_BROWSER_EXECUTABLE" not in e2.get("env", {}),
         "web : agent sans le droit `web` → enveloppe ordinaire (ni dossier, ni socat, ni lanceur)")
    r = berger("mcp-enveloppe", "alpha", "sonde"); dire(json.loads(r.stdout).get("web") is None, "web : serveur non déclaré web → enveloppe ordinaire")
    r = berger("mcp-enveloppe", "sansweb", "webnet")                      # revue du 18/10 : sans le droit, le réseau de l'hôte restait ouvert
    dire(r.returncode != 0 and "reseau" in r.stderr and "réseau" not in r.stdout,
         f"web = true + reseau = true : refusé TOUJOURS, même pour un agent sans le droit web ({(r.stderr or r.stdout).strip()[-120:]})")
    for srv, mot in (("webnet", "reseau"), ("webnav", "navigateur"), ("webmasque", "masqué"), ("webmal", "web = true")):
        r = berger("mcp-enveloppe", "retro", srv)
        dire(r.returncode != 0 and mot in r.stderr, f"web : refus {srv} ({r.stderr.strip()[-120:]})")
    # l'enveloppe de lancement : --proxy-server imposé en dernier, ceux de l'appelant retirés, le reste gardé dans l'ordre
    r = subprocess.run([str(i / "bin/berger-navigateur-web"), "--headless", "--proxy-server=http://ailleurs:1", "--no-proxy-server",
                        "--proxy-pac-url=http://x/p.pac", "--proxy-bypass-list=*", "--proxy-auto-detect", "--dump-dom", "http://permis.test/"],
                       env={"PATH": "/usr/bin:/bin", "BERGER_NAVIGATEUR": str(nav), "BERGER_FAUX_SEC": "1"}, capture_output=True, text=True, timeout=30)
    av = json.loads(r.stdout.splitlines()[0]).get("argv", []) if r.returncode == 0 and r.stdout.strip() else []
    dire(av[:3] == ["--headless", "--dump-dom", "http://permis.test/"] and av[3:] == ["--proxy-server=http://127.0.0.1:3128", "--proxy-bypass-list=<-loopback>", "--disable-dev-shm-usage"],
         f"berger-navigateur-web : proxy de l'enveloppe imposé, boucle locale par le proxy, options proxy de l'appelant retirées ({av})")
    r = subprocess.run([str(i / "bin/berger-navigateur-web"), "x"], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True, timeout=30)
    dire(r.returncode != 0 and "BERGER_NAVIGATEUR" in r.stderr, "berger-navigateur-web sans BERGER_NAVIGATEUR : refus clair")

    g["CONFIG"]["mcp"] = g["SERVEURS_MCP"]
    dire(any("mcp « inexistant »" in x for x in g["controler_proposition"]("gamma", "alpha", {"agent.conf": "nom = A\nmcp = inexistant\n"}))
         and any("ses propres réglages" in x for x in g["controler_proposition"]("alpha", "alpha", {"agent.conf": "nom = A\nmcp = sonde\n"})),
         "proposition : serveur non déclaré refusé ; un agent ne se donne pas de serveur à lui-même")

    # ── RELAIS (courtier/_mcp.py) et ENVELOPPE exécutée ──
    mcp = charger("courtier__mcp", i / "courtier/_mcp.py"); cmd = charger("outil__commandes", i / "courtier/outils/_commandes.py")
    masques_c = [str(coffre.parent), str(i / "agents"), str(i / "config.toml"), str(i / ".codex")]   # comme masques_courtier()
    def bac_essai(*a, **k):
        """L'enveloppe réelle ; l'installation jetable est sous /tmp (remplacé par le temporaire de l'agent) : elle est remontée
        en lecture seule AVANT les masques, comme ~/berger l'est en vrai (sous la racine en lecture seule)."""
        x = cmd.bac_a_sable(*a, **k); j = x.index("/tmp") + 1
        if not str(m).startswith("/tmp/"): return x
        sous = [y for q in a[2] if q.startswith(str(m)) and os.path.exists(q) for y in (["--tmpfs", q] if os.path.isdir(q) else ["--ro-bind", "/dev/null", q])]
        bt = env["BERGER_TMP_AGENTS"]; sous += ["--tmpfs", bt] if bt.startswith(str(m)) else []   # en vrai : hors de son /tmp
        x = x[:j] + ["--ro-bind", str(m), str(m)] + sous + x[j:]; k = x.index("--clearenv") if "--clearenv" in x else len(x)
        return x[:k] + [y for n, q in enumerate(sous) if q == "--tmpfs" for y in ("--remount-ro", sous[n + 1])] + x[k:]          # ses masques aussi (ceux sous /tmp sont sans objet en vrai)
    secret = lambda x: temoin in x or bool(__import__("re").search(r"sk-[A-Za-z0-9_-]{16,}", x))
    def parler(a, srv, messages, droits=None, bac=bac_essai):
        """Une session complète par des tubes (sans socket) → (réponses par id, autres messages, journal, alertes, sortie brute)."""
        lu, ec = os.pipe(); os.write(ec, (json.dumps({"serveur": srv}) + "\n" + "".join(json.dumps(x) + "\n" for x in messages)).encode()); os.close(ec)
        out, jl, al = bytearray(), [], []
        mcp.session(a, os.fdopen(lu, "rb"), out.extend, lambda: None, droits if droits is not None else set(agents[a][1][6:].split(", ")),
                    i / "bin/berger", bac, masques_c, secret, lambda *x: jl.append(x), lambda *x: al.append(x))
        ls = [json.loads(x) for x in out.decode().splitlines() if x.strip()]
        return {x["id"]: x for x in ls[1:] if "id" in x}, [x for x in ls[1:] if "id" not in x], jl, al, ls[:1]
    os.environ["PATH"] = env["PATH"]
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "essai", "version": "1"}}}
    appel = lambda id_, nom, **a: {"jsonrpc": "2.0", "id": id_, "method": "tools/call", "params": {"name": nom, "arguments": a}}
    valeur = "texte-transmis-éàü"
    rep, autres, jl, al, tete = parler("alpha", "sonde", [init, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                                                         {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, appel(3, "echo", texte=valeur),
                                                         appel(4, "echo", texte="avant " + temoin + " après"), appel(5, "piege")])
    dire(tete == [{"ok": True}], f"session : le courtier accepte (« ok ») puis relaie {tete}")
    dire(rep.get(1, {}).get("result", {}).get("serverInfo", {}).get("name") == "sonde-berger" and len(rep.get(2, {}).get("result", {}).get("tools", [])) == 5
         and rep.get(3, {}).get("result", {}).get("content", [{}])[0].get("text") == valeur, "le protocole passe tel quel (initialize, tools/list, tools/call)")
    dire(rep.get(4, {}).get("error", {}).get("message") == mcp.BLOQUEE and temoin not in json.dumps(rep), "filtre : valeur du coffre d'essai → réponse bloquée (erreur MCP)")
    dire(rep.get(5, {}).get("error", {}).get("message") == mcp.BLOQUEE, "filtre : forme de clé (outil piege) → réponse bloquée")
    dire(len(al) == 2, f"filtre : chaque réponse bloquée est notifiée au propriétaire ({len(al)})")
    appels = [x for x in jl if x[2] != "session"]
    dire([x[2] for x in appels] == ["initialize", "tools/list", "tools/call", "tools/call", "tools/call"]
         and [x[3] for x in appels][2:] == [["echo"], ["echo"], ["piege"]] and all(x[1] == "mcp:sonde" and x[0] == "alpha" for x in appels),
         "journal : une ligne par appel (agent, serveur, méthode, outil)")
    dire(all(valeur not in str(x) and temoin not in str(x) for x in jl) and all(" o" in x[5] and " ms" in x[5] for x in appels)
         and sum("BLOQUÉ" in x[5] for x in appels) == 2, "journal : durée, taille, verdict — aucune valeur (ni argument ni réponse)")
    dire([x[5].split(" (")[0] for x in jl if x[2] == "session"] == ["ouverte", "fermée"], "journal : session ouverte puis fermée (serveur arrêté)")
    # notification piégée (condition (4) du contrat) et enveloppe vue de dedans (condition (3)) : cibles posées comme le contrat
    ech = i / "agents/alpha/echantillons"; ech.mkdir(exist_ok=True)
    autre_tmp = Path(env["BERGER_TMP_AGENTS"]) / g["tmp_agent"]("beta").name; autre_tmp.mkdir(parents=True, exist_ok=True); (autre_tmp / "x").write_text("x")
    (ech / "berger-contrat-cibles.json").write_text(json.dumps({"piege": True, "lire": [str(coffre), str(i / "agents/beta/agent.conf"), str(i / "config.toml"),
                                                                                      str(i / "agents/alpha/agent.conf"), str(autre_tmp / "x")],
                                                              "ecrire": [str(i / "bin"), str(i / "agents/beta"), str(i), str(m), str(ech), "/tmp"]}))
    rep, autres, jl, al, _ = parler("alpha", "sonde", [init, {"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "id": 2, "method": "ping"}])
    dire(not autres and any("BLOQUÉ" in x[5] and x[2] == "notifications/message" for x in jl) and len(al) == 1,
         "filtre : notification du serveur qui contient une forme de clé → écartée, journalisée, notifiée")
    res = ech / "berger-contrat-resultat.json"; v = json.loads(res.read_text()) if res.is_file() else {}
    dire(v.get("lus") == [], f"enveloppe : coffre, autre agent, config, son agent.conf, temporaire d'un autre — illisibles ({v.get('lus')})")
    dire(v.get("ecrits") == [str(ech), "/tmp"], f"enveloppe : écrit dans « ecriture » et son /tmp seulement — ni bin/, ni autre agent, ni installation ({v.get('ecrits')})")
    dire(v.get("reseau") == "ferme", "enveloppe : réseau coupé")
    dire(v.get("env") == ["HOME", "LANG", "PATH", "PWD", "TMPDIR"], f"enveloppe : environnement vidé, puis le strict nécessaire (noms : {v.get('env')} ; PWD posé par bwrap)")
    dire(v.get("cwd") == str(ech), "enveloppe : le serveur tourne dans son dossier d'écriture")
    dire("--unshare-net" not in cmd.bac_a_sable(["x"], None, [], True, ecriture=[str(ech)], env={}) and "--clearenv" in cmd.bac_a_sable(["x"], None, [], True, env={}),
         "reseau = true : réseau gardé (environnement toujours vidé)")
    res.unlink(); (ech / "berger-contrat-cibles.json").unlink()
    rep, _, _, _, tete = parler("delta", "minimal", [init, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}], bac=cmd.bac_a_sable)
    dire(tete == [{"ok": True}] and rep.get(2, {}).get("result") == {"methode": "tools/list"},
         "enveloppe réelle, sans montage d'essai : un serveur sans fichier sous /tmp tourne (celui de la partie socket)")
    # bornes : 3 appels par minute, réponses de 1 Ko au plus
    rep, _, jl, _, _ = parler("alpha", "borne", [init, appel(2, "gros", n=100), appel(3, "gros", n=5000), appel(4, "echo", texte="a"), appel(5, "echo", texte="b")])
    dire("result" in rep.get(2, {}) and "trop grande" in rep.get(3, {}).get("error", {}).get("message", ""), "taille : une réponse au-delà de max_reponse → erreur, journalisée")
    dire("trop d'appels" in rep.get(4, {}).get("error", {}).get("message", "") and "trop d'appels" in rep.get(5, {}).get("error", {}).get("message", "")
         and sum("limite" in x[5] for x in jl) == 2, "débit : au-delà de max_par_minute → erreur sans atteindre le serveur, journalisée")
    # refus au lancement
    _, _, jl, _, tete = parler("alpha", "sonde", [init], droits={"borne"})
    dire(tete[:1] and tete[0].get("ok") is False and "n'a pas le droit" in tete[0].get("erreur", ""), "courtier : serveur hors du « mcp = » de l'agent → refus")
    _, _, _, _, tete = parler("gamma", "sonde", [init], droits={"sonde"})
    dire(tete[:1] and tete[0].get("ok") is False and "n'est pas dans" in tete[0].get("erreur", ""), "courtier : droit relu par berger mcp-enveloppe (une seule source)")
    for nom, faux in (("en échec", "/bin/false"), ("absent", str(m / "absent/bwrap"))):
        bac = lambda *a, **k: [faux, *bac_essai(*a, **k)[1:]]
        _, _, _, _, tete = parler("alpha", "sonde", [init], bac=bac)
        dire(tete[:1] and tete[0].get("ok") is False and "aucun serveur" in tete[0].get("erreur", ""), f"bwrap {nom} : aucun serveur, jamais de repli")

    # ── WEB : enveloppe réelle — sans accès, rien ne sort ; un accès ouvert APRÈS le lancement est vu sans relance ──
    W = charger("courtier__web", i / "courtier/_web.py")
    try: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close(); unix_web = True
    except OSError: unix_web = False
    if not unix_web: print("NON JOUÉ enveloppe web réelle (socat → socket du proxy) : AF_UNIX refusé ici (bac à sable) — joué par la porte tests")
    else:
        certificat_site, _, contextes_site = W.certificat_ephemere(["permis.test"])
        tls_site = contextes_site["permis.test"]
        site = socket.socket(); site.bind(("127.0.0.1", 0)); site.listen(16); port_site = site.getsockname()[1]; vus = []
        def servir_site():
            while True:
                try: c, _ = site.accept()
                except OSError: return
                vus.append(1)
                try: repondre_site(c, tls_site)
                except OSError: pass
        __import__("threading").Thread(target=servir_site, daemon=True).start()
        lu, ec = os.pipe(); out = bytearray(); fini = __import__("threading").Event()
        entree = os.fdopen(ec, "wb", buffering=0)
        def tourner():
            mcp.session("retro", os.fdopen(lu, "rb"), out.extend, fini.set, {"sondeweb"}, i / "bin/berger", bac_essai, masques_c, secret, lambda *x: None, lambda *x: None)
        th = __import__("threading").Thread(target=tourner, daemon=True); th.start()
        def appel_web(id_, **a):
            entree.write((json.dumps(appel(id_, "web", **a)) + "\n").encode()); fin = time.time() + 90
            while time.time() < fin:
                for l in out.decode(errors="replace").splitlines():
                    try: x = json.loads(l)
                    except ValueError: continue
                    if x.get("id") == id_: return json.loads(x["result"]["content"][0]["text"]) if "result" in x else {"erreur": x.get("error")}
                time.sleep(0.2)
            return {"erreur": "délai"}
        entree.write((json.dumps({"serveur": "sondeweb"}) + "\n" + json.dumps(init) + "\n").encode())
        urls = ["http://permis.test/", f"http://127.0.0.1:{port_site}/"]
        sans = appel_web(2, urls=urls, navigateur=True, marque="BERGER-SITE-PERMIS", direct=[["127.0.0.1", port_site]])
        dire(sans.get("urls") and not any(x.get("marque") for x in sans["urls"].values()) and not vus and sans.get("direct") == {f"127.0.0.1:{port_site}": "refuse"},
             f"web, sans accès : rien ne sort (navigateur par le proxy, boucle locale de l'hôte, connexion directe) ({sans})")
        jw = []; ouvre = []
        def ouvrir_site(adresse):
            if adresse not in (("8.8.8.8", 80), ("8.8.8.8", 443)): raise OSError("hors essai")
            ouvre.append(adresse); return socket.create_connection(("127.0.0.1", port_site), timeout=5)
        P = W.Proxy(["permis.test"], lambda *x: jw.append(x), resoudre=lambda h, p: {"permis.test": ["8.8.8.8"]}.get(h, []), ouvrir=ouvrir_site)
        P.tls_amont = ssl.create_default_context(cadata=certificat_site.decode())
        dossier_web = W.preparer_dossier(i / "courtier/mcp", "retro")
        P.ecouter(str(dossier_web / "proxy.sock"))
        (dossier_web / "cert.pem").write_bytes(P.certificat_pem)
        (dossier_web / "spki").write_text(P.empreinte + "\n")
        os.chmod(dossier_web / "cert.pem", 0o600); os.chmod(dossier_web / "spki", 0o600)
        try:
            avec = appel_web(3, urls=urls + ["http://ailleurs.test/"], navigateur=True, marque="BERGER-SITE-PERMIS")
            u = avec.get("urls") or {}
            dire(u.get("http://permis.test/", {}).get("marque") and not u.get(urls[1], {}).get("marque") and not u.get("http://ailleurs.test/", {}).get("marque"),
                 f"web, accès ouvert APRÈS le lancement : vu sans relance, permis.test reçu, autre nom et boucle locale de l'hôte non ({avec})")
            brut = appel_web(4, urls=["http://permis.test/"], marque="BERGER-SITE-PERMIS")
            dire(brut.get("urls", {}).get("http://permis.test/", {}).get("marque"),
                 f"web : HTTP brut avec accès reçoit permis.test (Host correct) ({brut})")
            ts = appel_web(5, tunnels=[{"hote": "permis.test", "sni": "permis.test"},
                                      {"hote": "ailleurs.test", "sni": "ailleurs.test"},
                                      {"hote": "permis.test", "sni": "ailleurs.test"}], marque="BERGER-SITE-PERMIS").get("tunnels", [])
            dire(len(ts) == 3 and ts[0].get("code") == 200 and ts[0].get("statut") == 200
                 and ts[0].get("marque") is True and ts[0].get("hello") is True and not ts[0].get("erreur")
                 and all(t.get("refuse") and not t.get("marque") and not t.get("erreur") for t in ts[1:])
                 and ("8.8.8.8", 443) in ouvre,
                 f"web : vrais CONNECT/ClientHello depuis l'enveloppe, positif reçu, autre domaine et SNI divergent refusés ({ts})")
            dire(any(x[:3] == ("CONNECT", "ailleurs.test", False) for x in jw)
                 and any(x[:3] == ("CONNECT", "permis.test", False) and "SNI" in x[3] for x in jw),
                 "web : les deux refus CONNECT et SNI sont journalisés")
            dire(len(vus) == len(ouvre) >= 1, f"web : le site n'a été joint que par le proxy ({len(vus)} connexion(s), {len(ouvre)} par le proxy)")
            dire(any(x[1] == "ailleurs.test" and x[2] is False for x in jw) and any(x[1] == "127.0.0.1" and x[2] is False for x in jw),
                 f"web : autre nom et boucle locale de l'hôte REFUSÉS au journal du proxy ({[x[:3] for x in jw]})")
        finally:
            P.arreter(); entree.close(); th.join(30); site.close()

    # ── CONTRAT : conditions (3) et (4) lues dans des sources machine (fichier de la sonde, journal du courtier) ──
    ct = runpy.run_path(str(SRC / "tests/contrat-moteur.py"), run_name="essai")
    def verdicts(resultat, journal_texte, flux=""):
        l = []; (ech / "berger-contrat-resultat.json").unlink(missing_ok=True)
        if resultat is not None: (ech / "berger-contrat-resultat.json").write_text(json.dumps(resultat))
        jf = m / "appels-essai.log"; jf.write_text("avant\n" + journal_texte)
        ct["conditions_mcp"](lambda ok, texte: l.append((bool(ok), texte)), "alpha", {"ecriture": [str(ech)], "reseau": False, "env": {}}, jf, len("avant\n"), flux)
        return l
    bon = {"lus": [], "ecrits": [], "reseau": "ferme", "env": ["HOME", "LANG", "PATH", "PWD", "TMPDIR"]}
    ligne = "2026-10-18 10:00:00\talpha\tmcp:berger-contrat\tnotifications/message\t\tREFUSÉ\tBLOQUÉ (secret dans la réponse), 80 o\n"
    l = verdicts(bon, ligne)
    dire(len(l) == 6 and all(x for x, _ in l), "contrat (3)/(4) : vert quand la sonde ne voit rien et que le piège est bloqué et journalisé")
    l = verdicts({**bon, "lus": ["/coffre"], "env": bon["env"] + ["SECRET_DE_SESSION"]}, ligne)
    dire([x for x, _ in l] == [True, False, True, True, False, True], "contrat (3) : rouge si un témoin est lu ou si l'environnement n'est pas vidé")
    l = verdicts(bon, "", flux="voici sk-" + "x" * 24)
    dire(l[-1][0] is False and "VUE" in l[-1][1], "contrat (4) : rouge si le moteur a vu la réponse piégée")
    l = verdicts(None, ligne)
    dire(not any(x for x, _ in l), "contrat (3)/(4) : serveur d'essai jamais lancé → rien n'est prouvé (rouge)")
    (ech / "berger-contrat-resultat.json").unlink(missing_ok=True)

    # ── CONTRAT : conditions (7) à (9), verdicts lus dans les réponses de la sonde (relais et proxy simulés ici ; le vrai
    # chemin — relais, courtier, enveloppe, navigateur — est celui du contrat lancé par le propriétaire) ──
    class FauxProxyC:
        dernier = None
        def __init__(self, noms, journal, resoudre, ouvrir): self.noms, self.journal, self.resoudre, self.ouvrir, self.ouvert = noms, journal, resoudre, ouvrir, False; FauxProxyC.dernier = self
        def ecouter(self, chemin): self.ouvert = True
        def arreter(self): self.ouvert = False
    WebReel = ct["charger_web"]()
    class FauxW:
        Proxy = FauxProxyC
        certificat_ephemere = staticmethod(WebReel.certificat_ephemere)
        @staticmethod
        def preparer_dossier(base, a): return m / "faux-web"
    def faux_relais(fuite=None):
        """Le serveur d'essai tel que l'enveloppe le rend : `fuite` = ce qui ne devrait PAS passer (sans-acces, nom, boucle, coffre)."""
        class R:
            def __init__(self, a): pass
            def fermer(self): pass
            def web(self, urls=(), navigateur=False, marque="", direct=(), tunnels=()):
                p = FauxProxyC.dernier if FauxProxyC.dernier and FauxProxyC.dernier.ouvert else None; out = {}
                for u in urls:
                    h = __import__("urllib.parse").parse.urlsplit(u).hostname
                    if u.startswith("file://"): out[u] = {"marque": "fichier-lisible" in marque or (fuite == "coffre" and "coffre" in u), "pre": "fichier-lisible" in marque, "octets": 9}
                    elif p is None: out[u] = {"marque": fuite == "sans-acces", "pre": False, "octets": 0}
                    else:
                        ok_ = h in p.noms and p.resoudre(h, 80) == ["8.8.8.8"]
                        if ok_: c = p.ouvrir(("8.8.8.8", 80)); c.sendall(b"GET / HTTP/1.1\r\n\r\n"); c.recv(100); c.close()
                        elif not (fuite == "boucle" and h == "127.0.0.1") and not (fuite == "nom" and h == "ailleurs.test"): p.journal("GET", h, False, "refusé")
                        out[u] = {"marque": ok_ or (fuite == "nom" and h == "ailleurs.test"), "pre": False, "octets": 10}
                for x in out.values(): x["execute"] = True
                ts = []
                for t in tunnels:
                    ok_ = t["hote"] == t["sni"] == "permis.test"
                    if ok_:
                        c = p.ouvrir(("8.8.8.8", 443)); c.sendall(b"temoin ClientHello"); c.recv(100); c.close()
                    p.journal("GET" if ok_ else "CONNECT", t["hote"], ok_, "SNI vérifié" if ok_ else "SNI divergent" if t["hote"] == "permis.test" else "autre nom")
                    ts.append({**t, "refuse": not ok_, "marque": ok_, "code": 200 if t["hote"] == "permis.test" else 403, "hello": True})
                return {"urls": out, "direct": {f"{h}:{q}": "refuse" for h, q in direct}, "tunnels": ts}
        return R
    def verdicts_web(fuite=None):
        l = []; gc = ct["conditions_web"].__globals__; gc["B"], gc["charger_web"], gc["Relais"] = i, lambda: FauxW, faux_relais(fuite); FauxProxyC.dernier = None
        cf = m / "coffre-contrat.json"; cf.write_text(json.dumps({"service": {"jeton": "x"}}))
        ct["conditions_web"](lambda ok, texte: l.append((bool(ok), texte)), "alpha", {"ecriture": [str(ech)]}, ct["Pose"](m / "pose-contrat.json"), str(cf))
        return l
    l = verdicts_web()
    dire(len(l) == 15 and all(x for x, _ in l), f"contrat (7)-(9) : {len(l)} contrôles, vert quand rien ne sort sans accès, le seul nom permis passe, le reste est refusé et journalisé, file:// du coffre illisible ({[t for x, t in l if not x]})")
    for fuite, n in (("sans-acces", "(7)"), ("nom", "(8) autre nom"), ("boucle", "(8) boucle locale"), ("coffre", "(9) coffre")):
        l = verdicts_web(fuite)
        dire(any(not x and t.startswith(n) for x, t in l), f"contrat {n} : rouge si {fuite} passe ({[t[:50] for x, t in l if not x]})")
    (i / "courtier/web").mkdir(parents=True, exist_ok=True); (i / "courtier/web/alpha.json").write_text("{}")
    l = verdicts_web(); (i / "courtier/web/alpha.json").unlink()
    dire(len(l) == 3 and not any(x for x, _ in l) and "VRAI accès" in l[0][1], "contrat (7)-(9) : non joué (rouge) si un vrai accès web est ouvert pour l'agent")

    # ── SOCKET : relais bin/berger-mcp ↔ vrai courtier ──
    try: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close(); unix = True
    except OSError: unix = False
    if not unix: print("NON JOUÉ relais ↔ courtier par socket : AF_UNIX refusé ici (bac à sable) — joué par la porte tests du courtier")
    else:
        co = subprocess.Popen([py, str(i / "courtier/courtier")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            fin = time.time() + 20
            while not (i / "courtier/mcp/alpha.sock").exists() and time.time() < fin: time.sleep(0.2)
            dire((i / "courtier/mcp/alpha.sock").exists() and not (i / "courtier/mcp/gamma.sock").exists(), "courtier : un socket par agent qui a un « mcp = »")
            dire(oct((i / "courtier/mcp").stat().st_mode & 0o777) == "0o700", "courtier : dossier des sockets en 700")
            entree = json.dumps(init) + "\n" + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n"
            r = subprocess.run([py, relais, "delta", "minimal"], input=entree, env=env, capture_output=True, text=True, timeout=60)
            ls = [json.loads(x) for x in r.stdout.splitlines() if x.strip()]
            dire(r.returncode == 0 and [x.get("id") for x in ls] == [1, 2] and ls[1].get("result") == {"methode": "tools/list"},
                 f"berger-mcp ↔ courtier : le protocole passe tel quel (code {r.returncode}, {r.stderr.strip()[-200:]})")
            r = subprocess.run([py, relais, "alpha", "beta-seul"], input="", env=env, capture_output=True, text=True, timeout=60)
            dire(r.returncode == 1 and "n'a pas le droit" in r.stderr, "berger-mcp : refus du courtier dit, code 1")
            r = subprocess.run([py, relais, "gamma", "sonde"], input="", env=env, capture_output=True, text=True, timeout=60)
            dire(r.returncode == 1 and "injoignable" in r.stderr, "berger-mcp : agent sans « mcp = » → aucun socket, refus")
            log = (i / "courtier/appels.log").read_text() if (i / "courtier/appels.log").exists() else ""
            dire("\tdelta\tmcp:minimal\ttools/list\t" in log and "\talpha\tmcp:beta-seul\tsession\t" in log, "courtier/appels.log : les appels MCP y sont")
        finally:
            co.terminate(); co.wait(10)

sys.exit(1 if ko else 0)
