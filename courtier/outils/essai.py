# -*- coding: utf-8 -*-
"""Outil de type « essai » : AUCUN système extérieur. Sert à tester le circuit des écritures validées.
L'écriture « noter » ajoute une ligne dans un fichier local du courtier (courtier/essai-ecritures.txt)."""
import datetime
from pathlib import Path


class Outil:
    def __init__(self, reglages, secret, verifier_hote):
        self.fichier = Path(__file__).resolve().parent.parent / "essai-ecritures.txt"
        self.verbes = {"lire": self.lire}
        self.ecritures = {"noter": (self.apercu_noter, self.noter)}

    def hotes(self): return {}

    def lire(self, args):
        """Relire les lignes écrites par l'essai."""
        return self.fichier.read_text().splitlines() if self.fichier.exists() else []

    def apercu_noter(self, args):
        """Écrire une ligne de texte dans le fichier d'essai du courtier."""
        if not args or not args[0].strip(): raise ValueError("texte attendu")
        return f"écrire « {args[0][:80]} » dans le fichier d'essai"

    def noter(self, args):
        with open(self.fichier, "a") as f: f.write(f"{datetime.datetime.now():%H:%M} {args[0][:80]}\n")
        return "ligne écrite"
