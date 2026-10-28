# -*- coding: utf-8 -*-
"""Outil de type « ssh » pour le courtier de Berger — des commandes FIXÉES À L'AVANCE sur un serveur distant.

Pour un agent d'administration en mur strict : il n'a ni SSH ni Internet, ni la clé. Le courtier se connecte pour lui
et ne lance QUE les commandes écrites dans config.toml (voir _commandes.py : lecture / actions / {arg}).

Réglages (config.toml, section [outils.<nom>]) :
  hote, port, utilisateur   le serveur (port 22 par défaut)
  cle_fichier               la clé privée SSH, sur le disque de l'installation (hors de portée de l'agent : masques)"""
import importlib.util, os, subprocess
from pathlib import Path

_spec = importlib.util.spec_from_file_location("outil__commandes", Path(__file__).with_name("_commandes.py"))
_base = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_base)


class Outil(_base.Base):
    def __init__(self, reglages, secret, verifier_hote):
        self.hote = reglages["hote"]; self.port = str(reglages.get("port", 22)); self.utilisateur = reglages["utilisateur"]
        self.cle = os.path.expanduser(reglages["cle_fichier"]); self.lieu = f"sur {self.utilisateur}@{self.hote}"
        super().__init__(reglages)

    def executer(self, cmd, verbe=None):
        r = subprocess.run(["ssh", "-i", self.cle, "-p", self.port, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                            "-o", "StrictHostKeyChecking=yes", f"{self.utilisateur}@{self.hote}", cmd],
                           capture_output=True, text=True, timeout=180)
        if r.returncode == 255: raise RuntimeError(f"connexion SSH impossible : {(r.stderr.strip().splitlines() or ['?'])[-1][:200]}")
        return r
