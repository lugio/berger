#!/usr/bin/env python3
"""Tue tout processus dont l'environnement porte BERGER_SUITE_MARQUE=<marque> : python3 tests/_tuer_marque.py <marque>
tests/suites.sh marque chaque suite (variable d'environnement, héritée par tous ses descendants, même ceux qui changent de session ou que la mort de
leur parent a laissés orphelins). TERM, courte attente, puis KILL. Affiche le nombre de processus visés ; ne vise jamais lui-même."""
import os
import signal
import sys
import time


def marques(marque):
    cible, moi = b"BERGER_SUITE_MARQUE=" + marque.encode() + b"\0", os.getpid()
    trouves = []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == moi:
            continue
        try:
            with open(f"/proc/{d}/environ", "rb") as f:
                if cible in f.read() + b"\0":
                    trouves.append(int(d))
        except OSError:
            continue
    return trouves


def main():
    marque = sys.argv[1]
    pids = marques(marque)
    for p in pids:
        try: os.kill(p, signal.SIGTERM)
        except OSError: pass
    fin = time.time() + 1.5
    while pids and time.time() < fin:
        time.sleep(0.1); pids = marques(marque)
    for p in pids:
        try: os.kill(p, signal.SIGKILL)
        except OSError: pass
    print(len(pids))


main()
