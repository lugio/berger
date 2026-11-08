#!/usr/bin/env python3
"""Mesure la mémoire d'une suite : python3 tests/_mesure_mem.py <fichier> <nom> -- <commande...>
Joue la commande (sorties et code de retour inchangés) et ajoute au fichier une ligne « pic_arbre_ko <TAB> plus_gros_processus_ko <TAB> nom » :
le pic de la somme des RSS de l'arbre de processus (relevé toutes les 0,2 s) et le plus gros processus (RUSAGE_CHILDREN). Sert à choisir n."""
import os
import resource
import subprocess
import sys
import threading
import time

PAGE_KO = os.sysconf("SC_PAGE_SIZE") // 1024


def arbre_ko(racine):
    """RSS (ko) de la racine et de tous ses descendants, d'après /proc."""
    enfants, rss = {}, {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                champs = f.read().rsplit(")", 1)[1].split()
            enfants.setdefault(int(champs[1]), []).append(int(d))
            with open(f"/proc/{d}/statm") as f:
                rss[int(d)] = int(f.read().split()[1]) * PAGE_KO
        except (OSError, IndexError, ValueError):
            continue
    total, pile = 0, [racine]
    while pile:
        p = pile.pop(); total += rss.get(p, 0); pile.extend(enfants.get(p, []))
    return total


def main():
    fichier, nom, commande = sys.argv[1], sys.argv[2], sys.argv[4:]
    p = subprocess.Popen(commande)
    pic, fini = [0], threading.Event()

    def releve():
        while not fini.is_set():
            pic[0] = max(pic[0], arbre_ko(p.pid)); fini.wait(0.2)
    th = threading.Thread(target=releve, daemon=True); th.start()
    rc = p.wait(); fini.set(); th.join(1)
    gros = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    with open(fichier, "a") as f:
        f.write(f"{pic[0]}\t{gros}\t{nom}\n")
    sys.exit(rc)


main()
