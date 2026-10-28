"""Isolation POSITIVE de Herdr pour les suites (28/10/2026, renvoi de la relecture croisée de tests-herdr-fuite).

Importé EN PREMIER par chaque suite de tests/suites.sh : il corrige l'environnement du processus lui-même, donc la suite est
isolée aussi quand on la lance seule (python3 tests/x.py), sans passer par tests/suites.sh. Retirer HERDR_* ne suffisait pas :
XDG_CONFIG_HOME ou HOME/.config retombaient sur le vrai herdr.sock. Désormais, quoi que la suite hérite d'un panneau Herdr :
  - BERGER_HERDR → un exécutable témoin qui ne fait rien (« false ») : bin/noyau/config.py HERDR ≠ « herdr », donc
    socket_herdr() ne lit plus que BERGER_HERDR_SOCKET, jamais HERDR_SOCKET_PATH, XDG_CONFIG_HOME ni HOME/.config ;
  - BERGER_HERDR_SOCKET → un chemin jetable qui n'existe pas (aucun serveur) ;
  - HERDR_*, XDG_CONFIG_HOME, tout BERGER_HERDR_SOCKET hérité → retirés.
Une suite qui veut SON faux Herdr le pose elle-même (BERGER_HERDR, BERGER_HERDR_SOCKET dans son env), après cet import.
Les RECETTES réelles (tests/tout.sh, tests/sonde-herdr*.py) n'importent pas ce module : elles restent connectées au vrai Herdr EXPRÈS."""
import os, shutil, tempfile

RETIREES = ("XDG_CONFIG_HOME", "BERGER_HERDR_SOCKET")


def temoin():
    return shutil.which("false") or "/bin/false"


def absent():
    return os.path.join(tempfile.gettempdir(), f"herdr-absent-{os.getpid()}.sock")      # jamais créé


def isoler(env):
    """Copie de env sans aucun chemin vers le vrai Herdr, avec un faux Herdr témoin imposé."""
    e = {k: v for k, v in env.items() if not k.startswith("HERDR_") and k not in RETIREES}
    e["BERGER_HERDR"] = temoin(); e["BERGER_HERDR_SOCKET"] = absent()
    return e


_e = isoler(os.environ)
for _k in [k for k in os.environ if k.startswith("HERDR_") or k in RETIREES]: del os.environ[_k]
os.environ["BERGER_HERDR"] = _e["BERGER_HERDR"]; os.environ["BERGER_HERDR_SOCKET"] = _e["BERGER_HERDR_SOCKET"]
