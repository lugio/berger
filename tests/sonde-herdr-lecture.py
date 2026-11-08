#!/usr/bin/env python3
"""Recette MANUELLE, propriétaire seulement : agent réel au repos, aucun service installé.

Usage : python3 tests/recette-herdr-lecture.py <agent> [codex|claude]
À jouer depuis l'installation possédant cet agent. Ne fait pas partie des portes.
Le résultat prouve lecture + acquittement + suppression par le moteur, pas le lot L4 entier.
RECETTE RÉELLE : connectée au VRAI Herdr EXPRÈS (n'importe pas tests/_herdr_isole.py). Les suites de tests/suites.sh, elles, sont isolées.
"""
import hashlib
import os
from pathlib import Path
import runpy
import secrets
import signal
import stat
import string
import subprocess
import sys
import tempfile
import time


def recette(arguments):
    if len(arguments) not in (1, 2):
        raise ValueError("agent requis, moteur optionnel")
    installation = Path(os.environ.get("BERGER_DIR") or Path(__file__).resolve().parent.parent)
    g = runpy.run_path(str(installation / "bin/berger"), run_name="recette")
    agent = arguments[0]
    if agent not in g["agents"](): raise ValueError("agent inconnu")
    dossier = g["dossier"](agent)
    if g["travail"](agent) != dossier:
        raise ValueError("recette limitée aux agents travaillant dans leur propre dossier")
    if dossier.is_symlink(): raise ValueError("dossier lié refusé")
    moteurs = g["herdr_ids"](agent).get("agents", {})
    moteur = arguments[1] if len(arguments) == 2 else next(iter(moteurs), None)
    if moteur not in moteurs or not g["au_repos"](moteurs[moteur]):
        raise ValueError("agent absent ou occupé : aucune sollicitation envoyée")

    # Le nom transmis à Herdr est relatif et neutre ; aucun contenu dans les arguments.
    temoin = ''.join(secrets.choice(string.ascii_lowercase) for _ in range(32))
    attendu = hashlib.sha256(temoin.encode()).hexdigest()
    ancien = signal.getsignal(signal.SIGTERM)
    def interrompre(numero, cadre): raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrompre)
    try:
        with tempfile.TemporaryDirectory(prefix="lecture-", dir=dossier) as temporaire:
            racine = Path(temporaire)
            if stat.S_IMODE(racine.stat().st_mode) != 0o700:
                raise ValueError("droits du dossier incorrects")
            relatif = racine.name
            message = racine / "message.md"
            recu = racine / "recu"
            texte = ("# Recette locale de lecture\n"
                     "Recette autorisée par le propriétaire, limitée à ce dossier de test. "
                     "Ne reproduis jamais la valeur ci-dessous dans une réponse, un argument de processus ou un journal. "
                     "Calcule son SHA-256 en mémoire avec un outil de lecture ou un script envoyé sur stdin. "
                     f"Écris uniquement l'empreinte hexadécimale dans {relatif}/recu, en fichier ordinaire 600. "
                     f"Puis supprime {relatif}/message.md après lecture. Ne modifie aucun autre fichier. "
                     "Réponds seulement : recette traitée.\n\n"
                     f"temoin: {temoin}\n")
            fd = os.open(message, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as f: f.write(texte)
            if stat.S_IMODE(message.stat().st_mode) != 0o600:
                raise ValueError("droits du fichier incorrects")
            invite = f"Recette locale : lis {relatif}/message.md et suis ses instructions de lecture et de nettoyage."
            g["herdr_api"]("agent.prompt", {"target": f"{agent}-{moteur}", "text": invite}, strict=True)
            fin = time.monotonic() + 180
            while time.monotonic() < fin:
                if recu.exists():
                    fd = os.open(recu, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    with os.fdopen(fd, "rb") as f:
                        meta = os.fstat(f.fileno())
                        if not stat.S_ISREG(meta.st_mode) or stat.S_IMODE(meta.st_mode) != 0o600:
                            raise ValueError("acquittement non conforme")
                        empreinte = f.read(129)
                    if empreinte.strip() == attendu.encode() and not os.path.lexists(message):
                        print("ok lecture réelle, empreinte conforme et suppression par l'agent")
                        break
                time.sleep(0.2)
            else: raise ValueError("lecture et nettoyage non prouvés dans le délai")
        if racine.exists(): raise ValueError("dossier de recette non nettoyé")
        print("ok nettoyage final du dossier de recette")
    finally:
        signal.signal(signal.SIGTERM, ancien)


if __name__ == "__main__":
    try: recette(sys.argv[1:])
    except (ValueError, OSError, subprocess.TimeoutExpired):
        print("ÉCHEC recette non admise ; aucun contenu privé affiché", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("ÉCHEC recette interrompue ; nettoyage demandé", file=sys.stderr)
        sys.exit(130)
