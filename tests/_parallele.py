"""Suites jouées à la fois et rejeu en groupes de processus (tests/suites.sh, tests/herdr-fuite.py)."""
import os
import signal
import subprocess
import sys
import time

_ACTIFS = set()    # groupes de processus des rejeux en cours (tués à l'interruption)


def parallele(env=None):
    """Suites à la fois : 1 par défaut ; BERGER_SUITES_PARALLELE n'accepte que 1, 2, 3 ou 4 (sinon 1 : voir refus()). Même règle que suites.sh."""
    v = (os.environ if env is None else env).get("BERGER_SUITES_PARALLELE", "")
    return int(v) if v in ("1", "2", "3", "4") else 1


def refus(env=None):
    """Le refus nommé d'une valeur invalide de BERGER_SUITES_PARALLELE, ou None (absente, vide ou valide). Jamais d'exception."""
    v = (os.environ if env is None else env).get("BERGER_SUITES_PARALLELE", "")
    if v == "" or v in ("1", "2", "3", "4"):
        return None
    return f"BERGER_SUITES_PARALLELE=« {v[:40]} » refusé : un entier de 1 à 4 est attendu, 1 utilisé"


def delai(env=None):
    """Délai maximal d'une suite, en secondes (BERGER_SUITE_DELAI, 1200 par défaut ; valeur invalide = 1200)."""
    v = (os.environ if env is None else env).get("BERGER_SUITE_DELAI", "")
    return int(v) if v.isascii() and v.isdigit() and 0 < len(v) <= 6 and int(v) > 0 else 1200


def tuer_groupe(pgid, attente=2.0):
    """TERM au groupe, courte attente, puis KILL : les descendants ne survivent pas à leur suite."""
    try:
        os.killpg(pgid, signal.SIGTERM)
    except OSError:
        return
    fin = time.time() + attente
    while time.time() < fin:
        try:
            os.killpg(pgid, 0)
        except OSError:
            return
        time.sleep(0.1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass


def groupe_run(args, env, cwd, timeout):
    """Comme subprocess.run(capture_output) mais dans son propre groupe de processus : (code, sortie) ; 124 au délai dépassé,
    et dans tous les cas plus aucun descendant à la fin."""
    p = subprocess.Popen(args, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    _ACTIFS.add(p.pid)
    try:
        try:
            sortie, _ = p.communicate(timeout=timeout)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            tuer_groupe(p.pid)
            sortie, _ = p.communicate()
            rc, sortie = 124, (sortie or "") + f"\ndélai dépassé ({timeout} s) : groupe de processus arrêté"
        try:
            os.killpg(p.pid, signal.SIGKILL)       # un descendant resté derrière une suite terminée
        except OSError:
            pass
        return rc, sortie
    finally:
        _ACTIFS.discard(p.pid)


def installer_signaux():
    """TERM / INT : tuer les groupes des rejeux en cours (TERM, attente courte, KILL) puis sortir sans attendre les fils."""
    def arret(signum, _frame):
        for g in list(_ACTIFS):
            tuer_groupe(g, 1.5)
        os._exit(128 + signum)
    signal.signal(signal.SIGTERM, arret)
    signal.signal(signal.SIGINT, arret)
