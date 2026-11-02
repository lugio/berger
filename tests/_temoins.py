#!/usr/bin/env python3
"""Sockets TÉMOINS de Herdr pour tests/suites.sh : python3 tests/_temoins.py <racine> <N> <fichier-connexions> <fichier-pret>
Pour chacune des N suites (n° i), quatre sockets écoutent à la place du vrai serveur Herdr, sur les quatre chemins par lesquels une suite pourrait
l'atteindre : h-i.sock (HERDR_SOCKET_PATH), b-i.sock (BERGER_HERDR_SOCKET hérité), x-i/herdr/herdr.sock (XDG_CONFIG_HOME=x-i) et
m-i/.config/herdr/herdr.sock (repli du HOME jetable m-i). Chaque connexion ajoute une ligne « i vecteur » au fichier des connexions. Une fois tout
à l'écoute, le fichier « pret » est écrit. Code 3 : les sockets ne peuvent pas écouter ici (bac à sable) → le lanceur dit NON JOUÉ."""
import os
import selectors
import signal
import socket
import sys

racine, n, connexions, pret = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
sel = selectors.DefaultSelector()
try:
    for i in range(n):
        for vecteur, chemin in (("HERDR_SOCKET_PATH", f"{racine}/h-{i}.sock"), ("BERGER_HERDR_SOCKET", f"{racine}/b-{i}.sock"),
                                ("XDG_CONFIG_HOME", f"{racine}/x-{i}/herdr/herdr.sock"), ("HOME/.config", f"{racine}/m-{i}/.config/herdr/herdr.sock")):
            os.makedirs(os.path.dirname(chemin), exist_ok=True)
            so = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); so.bind(chemin); so.listen(16); so.setblocking(False)
            sel.register(so, selectors.EVENT_READ, (i, vecteur))
except OSError as e:
    print(f"sockets témoins impossibles ici : {e}", file=sys.stderr); sys.exit(3)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
open(pret, "w").close()
while True:
    for cle, _ in sel.select():
        try: c, _ = cle.fileobj.accept()
        except OSError: continue
        c.close()
        with open(connexions, "a") as f: f.write(f"{cle.data[0]} {cle.data[1]}\n")
