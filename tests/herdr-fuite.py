#!/usr/bin/env python3
"""Fuite vers le VRAI Herdr (28/10/2026) : les développeurs et le rejeu tournent dans des panneaux Herdr et héritent de
HERDR_SOCKET_PATH (et de XDG_CONFIG_HOME, dont dépend le chemin par défaut du socket) ; une suite qui part de os.environ parlait au
vrai serveur (~80 espaces « P · un/deux/mdp/secr/pf » dans la session réelle).
Isolation POSITIVE (tests/_herdr_isole.py, tests/suites.sh) : un faux Herdr imposé, jamais le vrai. Ici :
  1. sans socket (joué partout) : le lanceur impose le faux Herdr et retire HERDR_*, XDG_CONFIG_HOME, BERGER_HERDR_SOCKET hérité (une suite
     sonde échoue sinon ; son code de retour et sa ligne témoin sont vérifiés) ; la résolution du socket (socket_herdr) sans isolation
     tombe sur le chemin hérité (CONTRÔLE POSITIF), avec l'isolation sur aucun des quatre chemins réels ; chaque suite de suites.sh importe
     tests/_herdr_isole.py (isolée aussi lancée seule) ;
  2. avec sockets (NON JOUÉ dans un bac à sable qui les refuse, jamais ok) : des sockets TÉMOINS écoutent sur chaque chemin réel
     (HERDR_SOCKET_PATH, XDG_CONFIG_HOME/herdr/herdr.sock, BERGER_HERDR_SOCKET hérité) ; un client Herdr SANS isolation les atteint
     (contrôle positif : sans lui, « 0 connexion » ne prouverait rien), AVEC isolation non ; puis CHAQUE suite de suites.sh est lancée seule,
     environnement hostile, code de retour vérifié (une suite qui plante avant l'appel dangereux ne prouve rien) : 0 connexion.
Les recettes réelles (tests/tout.sh, sonde-herdr*.py) restent connectées au vrai Herdr EXPRÈS : elles ne sont pas jouées ici.
Usage : python3 tests/herdr-fuite.py (0 = tout passe)"""
import concurrent.futures, os, re, shutil, socket, subprocess, sys, tempfile, threading
from pathlib import Path

T = Path(__file__).resolve().parent
SRC = T.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


SUITES = [n for n in re.findall(r"^suite (\S+\.py)", (T / "suites.sh").read_text(), re.M) if n != "herdr-fuite.py"]
# Les suites qui atteignaient le vrai Herdr (relecture croisée du 28/10/2026), plus celles de la fuite d'origine.
SUITES_EXPOSEES = [n for n in ("equipe-ouverture.py", "regle-go.py", "missions.py", "agent-appliquer.py", "bibliotheque-projets.py",
                               "domaines.py", "installation.py", "espaces.py") if n in SUITES]
PROG = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\nif %s: import _herdr_isole\n"
        "from noyau.herdr import socket_herdr, herdr_api\nprint('CHEMIN', socket_herdr()); herdr_api('ping', {})\n")


def client(install, env, isole):
    r = subprocess.run([sys.executable, "-c", PROG % (str(SRC / "bin"), str(T), "True" if isole else "False")],
                       env={**env, "BERGER_DIR": str(install)}, capture_output=True, text=True, timeout=60)
    m = re.search(r"^CHEMIN (.*)$", r.stdout, re.M)
    return r.returncode, (m.group(1) if m else None)


# ── 1. Sans socket : joué partout ────────────────────────────────────────────────────────────────────────────────────────
SONDE = ("import os, sys\nv = sorted(k for k in os.environ if k.startswith('HERDR_') or k in ('XDG_CONFIG_HOME', 'BERGER_HERDR_SOCKET_HERITE'))\n"
         "h, s = os.environ.get('BERGER_HERDR'), os.environ.get('BERGER_HERDR_SOCKET')\n"
         "bon = not v and h not in (None, 'herdr') and os.path.basename(h) == 'false' and s and s != '/herite/herdr.sock' and not os.path.exists(s)\n"
         "print('ok    environnement isolé' if bon else 'ÉCHEC fuite : %s %s %s' % (v, h, s)); sys.exit(0 if bon else 1)\n")
with tempfile.TemporaryDirectory(prefix="hf") as t:
    t = Path(t)
    (t / "tests").mkdir(); shutil.copy2(T / "suites.sh", t / "tests/suites.sh"); (t / "tests/sonde.py").write_text(SONDE)
    herite = {**os.environ, "HERDR_SOCKET_PATH": "/herite/herdr.sock", "HERDR_PANE_ID": "pane-temoin", "HERDR_WORKSPACE_ID": "espace-temoin",
              "HERDR_ENV": "1", "XDG_CONFIG_HOME": "/herite/config", "BERGER_HERDR_SOCKET": "/herite/herdr.sock", "BERGER_HERDR": "herdr",
              "SUITE_SEULE": "sonde.py"}
    r = subprocess.run(["bash", str(t / "tests/suites.sh")], env=herite, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0 and "1 contrôles" in r.stdout,       # la sonde a tourné (sa ligne « ok » est comptée) ET vu un environnement isolé
         "lanceur : faux Herdr imposé, HERDR_*, XDG_CONFIG_HOME et BERGER_HERDR_SOCKET hérités retirés (code 0, sonde jouée)")

with tempfile.TemporaryDirectory(prefix="hf") as t:
    t = Path(t); inst = t / "inst"; inst.mkdir(); (inst / "config.toml").write_text('proprietaire = "Proprio"\n')
    (t / "xdg/herdr").mkdir(parents=True); (t / "home/.config/herdr").mkdir(parents=True)
    base = {k: v for k, v in os.environ.items() if not k.startswith(("HERDR_", "BERGER_HERDR")) and k != "XDG_CONFIG_HOME"}
    # contrôle positif : sans isolation, la résolution tombe sur chacun des chemins réels
    for nom, extra, attendu in (("HERDR_SOCKET_PATH", {"HERDR_SOCKET_PATH": str(t / "h.sock")}, str(t / "h.sock")),
                                ("XDG_CONFIG_HOME", {"XDG_CONFIG_HOME": str(t / "xdg")}, str(t / "xdg/herdr/herdr.sock")),
                                ("HOME/.config", {"HOME": str(t / "home")}, str(t / "home/.config/herdr/herdr.sock"))):
        env = {**base, **extra}
        rc, ch = client(inst, env, False)
        dire(ch == attendu, f"contrôle positif : sans isolation, la résolution suit {nom} (chemin réel atteint)")
        rc, ch = client(inst, env, True)
        dire(rc == 0 and ch is not None and ch not in (attendu, str(t / "h.sock"), str(t / "xdg/herdr/herdr.sock"), str(t / "home/.config/herdr/herdr.sock")),
             f"avec isolation (import _herdr_isole) : {nom} n'est plus suivi, code de retour 0 ({ch})")
    # chaque suite importe l'isolation EN PREMIER (lancée seule, elle est isolée)
    sans = [n for n in SUITES if not re.search(r"^import os as _os, sys as _sys;.*import _herdr_isole", (T / n).read_text(), re.M)]
    dire(not sans, f"chaque suite de suites.sh importe tests/_herdr_isole.py ({len(SUITES)} suites){' — manque : ' + ', '.join(sans) if sans else ''}")

# ── 2. Avec sockets : NON JOUÉ dans un bac à sable qui les refuse ────────────────────────────────────────────────────────
try: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close()
except OSError:
    print("NON JOUÉ socket AF_UNIX impossible dans cet environnement (bac à sable) : connexions aux sockets témoins non prouvées")
    sys.exit(1 if ko else 0)


class Temoin:
    """Socket qui écoute à la place du vrai serveur et compte les connexions."""
    def __init__(self, chemin):
        self.n = 0; self.stop = False
        self.so = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); self.so.bind(str(chemin)); self.so.listen(64); self.so.settimeout(0.2)
        self.th = threading.Thread(target=self.boucle, daemon=True); self.th.start()

    def boucle(self):
        while not self.stop:
            try: c, _ = self.so.accept()
            except socket.timeout: continue
            except OSError: break
            self.n += 1; c.close()

    def fin(self):
        self.stop = True; self.so.close(); self.th.join(2)


with tempfile.TemporaryDirectory(prefix="hf") as t:
    t = Path(t); inst = t / "inst"; inst.mkdir(); (inst / "config.toml").write_text('proprietaire = "Proprio"\n')
    (t / "xdg/herdr").mkdir(parents=True)
    vecteurs = {"HERDR_SOCKET_PATH": (t / "h.sock", {"HERDR_SOCKET_PATH": str(t / "h.sock")}),
                "XDG_CONFIG_HOME": (t / "xdg/herdr/herdr.sock", {"XDG_CONFIG_HOME": str(t / "xdg")}),
                "BERGER_HERDR_SOCKET": (t / "b.sock", {"BERGER_HERDR_SOCKET": str(t / "b.sock"), "BERGER_HERDR": "/bin/true"})}
    temoins = {k: Temoin(v[0]) for k, v in vecteurs.items()}
    hostile = {**{k: v for k, v in os.environ.items() if not k.startswith(("HERDR_", "BERGER_HERDR")) and k != "XDG_CONFIG_HOME"},
               "HERDR_PANE_ID": "pane-temoin", "HERDR_WORKSPACE_ID": "espace-temoin", "HERDR_ENV": "1"}
    for k, (_, extra) in vecteurs.items():           # contrôle positif PUIS isolé, vecteur par vecteur
        avant = temoins[k].n; client(inst, {**hostile, **extra}, False); apres = temoins[k].n
        dire(apres > avant, f"contrôle positif : un client Herdr sans isolation atteint le témoin {k}")
        client(inst, {**hostile, **extra}, True)
        dire(temoins[k].n == apres, f"un client Herdr isolé n'atteint pas le témoin {k}")
    tous = {"HERDR_SOCKET_PATH": str(t / "h.sock"), "XDG_CONFIG_HOME": str(t / "xdg"), "BERGER_HERDR_SOCKET": str(t / "b.sock"), "BERGER_HERDR": "/bin/true"}
    for n in temoins.values(): n.n = 0

    def joue(suite):
        r = subprocess.run([sys.executable, str(T / suite)], env={**hostile, **tous}, capture_output=True, text=True, timeout=900, cwd=SRC)
        return suite, r.returncode, r.stdout + r.stderr
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for suite, rc, sortie in ex.map(joue, SUITES_EXPOSEES):
            if rc != 0: dire(False, f"{suite} lancée seule, environnement hostile : code {rc} (une suite qui plante ne prouve rien) : {sortie[-300:]!r}")
    dire(len(SUITES_EXPOSEES) == 8 and all(x.n == 0 for x in temoins.values()),
         f"{len(SUITES_EXPOSEES)} suites exposées lancées seules, environnement hostile : 0 connexion aux témoins ({', '.join(f'{k}={x.n}' for k, x in temoins.items())})")
    for x in temoins.values(): x.fin()
sys.exit(1 if ko else 0)
