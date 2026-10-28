# -*- coding: utf-8 -*-
"""Outil de type « scripts » pour le courtier de Berger — lancer, HORS bac à sable, une liste FERMÉE de scripts.

Pour un agent en mur strict qui avait l'habitude de lancer ses propres scripts (qui lisent le coffre eux-mêmes).
Réglages : `dossier` (où sont les scripts), `interpreteur` (facultatif, ex. un python de venv), `autorises` = noms des
scripts permis. 🛑 N'y mettre QUE des scripts en LECTURE SEULE : le courtier les lance sans validation.
Arguments : 5 au plus, caractères simples, jamais de shell. Sortie : 15 000 caractères au plus.
Le script reçoit dans BERGER_AGENT l'agent qui demande (posé par le courtier dans self.contexte), pour ses registres."""
import importlib.util, os, re, subprocess
from pathlib import Path

_spec = importlib.util.spec_from_file_location("outil__contexte", Path(__file__).with_name("_contexte.py"))
_contexte = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_contexte)   # contexte propre à chaque appel


class Outil:
    contexte = _contexte.ContexteDeLAppel({})                        # posé par le courtier pour CET appel

    def __init__(self, reglages, secret, verifier_hote):
        self.dossier = Path(os.path.expanduser(reglages["dossier"]))
        self.interpreteur = os.path.expanduser(reglages.get("interpreteur", "python3"))
        self.verbes = {}
        for nom in reglages.get("autorises", []):
            def lancer(args, nom=nom): return self.lancer(nom, args)
            lancer.__doc__ = f"Lancer {nom} (lecture seule) avec 5 arguments au plus."
            self.verbes[nom] = lancer

    def hotes(self): return {}

    def lancer(self, nom, args):
        script = (self.dossier / nom).resolve()
        if not script.is_file() or script.parent != self.dossier.resolve(): raise PermissionError(f"script introuvable : {nom}")
        for a in args:
            if not re.fullmatch(r"[\w./:=,+-]{1,80}", a): raise ValueError(f"argument refusé : {a[:30]}")
        env = {**os.environ, "BERGER_AGENT": self.contexte.get("agent", "")}       # qui demande : posé par le courtier, jamais par l'agent
        r = subprocess.run([self.interpreteur, str(script), *args[:5]], capture_output=True, text=True, timeout=600, cwd=self.dossier, env=env)
        sortie = (r.stdout + ("\n[erreurs]\n" + r.stderr[-2000:] if r.returncode and r.stderr else ""))
        return {"code": r.returncode, "sortie": sortie[-15000:], "coupe": len(sortie) > 15000}
