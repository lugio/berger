# -*- coding: utf-8 -*-
"""Outil de type « commandes » pour le courtier de Berger — des commandes FIXÉES À L'AVANCE sur CETTE machine.

Pour un agent en mur strict qui a besoin de gestes hors de son bac à sable : tests qui parlent à une base locale,
git push, déploiement, installation de paquets… Le courtier les lance HORS bac à sable, dans le dossier `dossier`,
et seulement celles écrites dans config.toml (voir _commandes.py : lecture / actions / {arg}).

Réglages (config.toml, section [outils.<nom>]) :
  dossier   où les commandes sont lancées (ex. le dossier d'un projet)
  delai     durée maximale d'une commande, en secondes (600 par défaut)
  bac_a_sable  verbes qui exécutent du code qu'un AGENT peut modifier (ex. ["verify"] dans le dépôt d'un agent) :
            lancés dans un bac à sable (voir _commandes.bac_a_sable) ; reseau = true si ces tests parlent à localhost."""
import importlib.util, os, subprocess
from pathlib import Path

_spec = importlib.util.spec_from_file_location("outil__commandes", Path(__file__).with_name("_commandes.py"))
_base = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_base)


class Outil(_base.Base):
    def __init__(self, reglages, secret, verifier_hote):
        self.dossier = Path(os.path.expanduser(reglages["dossier"])); self.delai = int(reglages.get("delai", 600))
        self.lieu = f"dans {reglages['dossier']}"
        self.bac = set(reglages.get("bac_a_sable", [])); self.reseau = bool(reglages.get("reseau")); self.masques = reglages.get("masques", [])
        super().__init__(reglages)

    def executer(self, cmd, verbe=None):
        if not self.dossier.is_dir(): raise RuntimeError(f"dossier introuvable : {self.dossier}")
        env = dict(os.environ); h = str(Path.home())
        env["PATH"] = f"{h}/.local/bin:{h}/.local/share/mise/shims:" + env.get("PATH", "/usr/local/bin:/usr/bin:/bin"); env.update(_base.ENV_GIT)
        try:
            construire = (lambda args: _base.bac_a_sable(args, self.dossier, self.masques, self.reseau)) if verbe in self.bac else None
            return _base._transport.executer_shell(cmd, construire=construire, cwd=self.dossier, capture_output=True, text=True, timeout=self.delai, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"commande trop longue (plus de {self.delai} s) : arrêtée")
