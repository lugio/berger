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
     (HERDR_SOCKET_PATH, XDG_CONFIG_HOME/herdr/herdr.sock, BERGER_HERDR_SOCKET hérité, et le repli HOME/.config/herdr/herdr.sock d'un
     HOME JETABLE) ; un client Herdr SANS isolation les atteint (contrôle positif : sans lui, « 0 connexion » ne prouverait rien), AVEC
     isolation non ; tests/sonde-shebang.py, lancée directement, est isolée et rejouée de même. Le rejeu de TOUTES les suites n'est plus
     fait ici (il doublait la durée de la porte) : tests/suites.sh joue CHAQUE suite, à son passage normal, dans cet environnement hostile
     (un socket témoin par suite et par chemin, tests/_temoins.py) et échoue au nom de la suite qui s'y connecte ; vérifié par
     tests/parallele-memoire.py (une suite témoin qui se connecte fait échouer la passe).
Les recettes réelles (tests/tout.sh, sonde-herdr*.py) restent connectées au vrai Herdr EXPRÈS : elles ne sont pas jouées ici.
Usage : python3 tests/herdr-fuite.py (0 = tout passe)"""
import os, re, shutil, socket, subprocess, sys, tempfile, threading
from pathlib import Path

T = Path(__file__).resolve().parent
sys.path.insert(0, str(T))
from _parallele import delai, groupe_run, installer_signaux
SRC = T.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


SUITES = [n for n in re.findall(r"^suite (\S+\.py)", (T / "suites.sh").read_text(), re.M) if n != "herdr-fuite.py"]
# TOUTES les suites sont jouées avec les sockets témoins (relecture croisée du 28/10/2026 : en choisir huit sur cent neuf ne prouvait
# rien pour les autres) PAR suites.sh, à leur passage normal ; ici, seule la sonde qui se lance directement.
SONDES_ISOLEES = ["sonde-shebang.py"]
A_REJOUER = SUITES + SONDES_ISOLEES
PROG = ("import sys; sys.path.insert(0, %r); sys.path.insert(0, %r)\nif %s: import _herdr_isole\n"
        "from noyau.herdr import socket_herdr, herdr_api\nprint('CHEMIN', socket_herdr()); herdr_api('ping', {})\n")


def client(install, env, isole):
    r = subprocess.run([sys.executable, "-c", PROG % (str(SRC / "bin"), str(T), "True" if isole else "False")],
                       env={**env, "BERGER_DIR": str(install)}, capture_output=True, text=True, timeout=60)
    m = re.search(r"^CHEMIN (.*)$", r.stdout, re.M)
    return r.returncode, (m.group(1) if m else None)


# ── 1. Sans socket : joué partout ────────────────────────────────────────────────────────────────────────────────────────
SONDE = ("import os, sys\n"
         "fuite = sorted(k for k, v in os.environ.items() if k.startswith(('HERDR_', 'BERGER_HERDR')) or k == 'XDG_CONFIG_HOME' if '/herite' in v or v == 'herdr')\n"
         "h = os.environ.get('BERGER_HERDR')\n"
         "bon = not fuite and h not in (None, 'herdr') and os.path.basename(h) in ('false', 'true')   # faux Herdr du lanceur, ou environnement hostile vers ses témoins\n"
         "print('ok    environnement isolé' if bon else 'ÉCHEC fuite : %s %s' % (fuite, h)); sys.exit(0 if bon else 1)\n")
installer_signaux()
with tempfile.TemporaryDirectory(prefix="hf") as t:
    t = Path(t)
    (t / "tests").mkdir(); shutil.copy2(T / "suites.sh", t / "tests/suites.sh"); (t / "tests/sonde.py").write_text(SONDE)
    herite = {**os.environ, "HERDR_SOCKET_PATH": "/herite/herdr.sock", "HERDR_PANE_ID": "pane-temoin", "HERDR_WORKSPACE_ID": "espace-temoin",
              "HERDR_ENV": "1", "XDG_CONFIG_HOME": "/herite/config", "BERGER_HERDR_SOCKET": "/herite/herdr.sock", "BERGER_HERDR": "herdr",
              "SUITE_SEULE": "sonde.py", "BERGER_SUITES_VERROU": str(t / "verrou-jetable.lock")}   # son temporaire n'a pas de .git : sans ce verrou jetable, « forge locale introuvable »
    (t / "verrou-jetable.lock").write_text("")
    herite.pop("BERGER_SUITES_VERROU_TENU", None)           # lancée seule comme par une porte : le verrou jetable est pris pour de vrai
    r = subprocess.run(["bash", str(t / "tests/suites.sh")], env=herite, capture_output=True, text=True, timeout=120)
    dire(r.returncode == 0 and "1 contrôles" in r.stdout,       # la sonde a tourné (sa ligne « ok » est comptée) ET vu un environnement isolé
         "lanceur : faux Herdr imposé, HERDR_*, XDG_CONFIG_HOME et BERGER_HERDR_SOCKET hérités retirés (code 0, sonde jouée)"
         + ("" if r.returncode == 0 and "1 contrôles" in r.stdout else f" — code {r.returncode} : {' '.join((r.stdout + r.stderr).split())[-500:]}"))

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
    # chaque suite (et la sonde lancée directement) importe l'isolation EN PREMIER (lancée seule, elle est isolée)
    sans = [n for n in A_REJOUER if not re.search(r"^import os as _os, sys as _sys;.*import _herdr_isole", (T / n).read_text(), re.M)]
    dire(not sans, f"chaque suite de suites.sh et sonde-shebang.py importent tests/_herdr_isole.py ({len(A_REJOUER)} fichiers){' — manque : ' + ', '.join(sans) if sans else ''}")

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
    (t / "xdg/herdr").mkdir(parents=True); (t / "home/.config/herdr").mkdir(parents=True)
    vecteurs = {"HERDR_SOCKET_PATH": (t / "h.sock", {"HERDR_SOCKET_PATH": str(t / "h.sock")}),
                "HOME/.config (repli)": (t / "home/.config/herdr/herdr.sock", {"HOME": str(t / "home")}),
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
    # le rejeu : les trois chemins hérités ET un HOME jetable dont le repli HOME/.config/herdr/herdr.sock a son propre témoin
    tous = {"HERDR_SOCKET_PATH": str(t / "h.sock"), "XDG_CONFIG_HOME": str(t / "xdg"), "BERGER_HERDR_SOCKET": str(t / "b.sock"), "BERGER_HERDR": "/bin/true",
            "HOME": str(t / "home")}
    for n in temoins.values(): n.n = 0

    # Sous un HOME jetable, un raccourci mise de la vraie maison échoue (« config.toml are not trusted », y compris python3) : le PATH du
    # rejeu est celui des suites de tests/suites.sh — sans « …/mise/shims », précédé d'un python3 qui EST l'interpréteur réel.
    (t / "py").mkdir(); (t / "py/python3").symlink_to(os.path.realpath(sys.executable))
    tous["PATH"] = os.pathsep.join([str(t / "py")] + [d for d in os.environ.get("PATH", "").split(os.pathsep) if not re.search(r"/mise/shims/*$", d)])
    for suite in SONDES_ISOLEES:       # les suites, elles, sont jouées en environnement hostile par suites.sh lui-même (une seule fois chacune)
        rc, sortie = groupe_run([sys.executable, str(T / suite)], {**hostile, **tous}, SRC, delai())
        if rc != 0:
            causes = [l[:300] for l in sortie.splitlines() if re.match(r"ÉCHEC|FAIL|ERROR|Traceback|\w*(Error|Exception)", l)][-6:]
            dire(False, f"{suite} lancée seule, environnement hostile : code {rc} (une sonde qui plante ne prouve rien) : {causes or sortie[-300:]!r}")
    dire(all(x.n == 0 for x in temoins.values()),
         f"{', '.join(SONDES_ISOLEES)} lancée seule, environnement hostile, HOME jetable : "
         f"0 connexion aux témoins ({', '.join(f'{k}={x.n}' for k, x in temoins.items())})")
    for x in temoins.values(): x.fin()
sys.exit(1 if ko else 0)
