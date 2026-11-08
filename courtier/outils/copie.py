# -*- coding: utf-8 -*-
"""Outil de type « copie » pour le courtier de Berger — les commandes d'un DÉVELOPPEUR d'équipe, dans SA copie.

Un développeur d'équipe (agent jetable ouvert par `berger equipe ouvrir`) travaille dans sa copie du dépôt (git
worktree), sur sa branche, avec son application et sa base. Ses commandes sont FIXÉES dans config.toml (voir
_commandes.py : lecture / actions / {arg}) et le courtier y remplace, d'après l'agent.conf de CELUI QUI DEMANDE :
  {copie}   sa copie du dépôt (les commandes y sont lancées)      {branche}  sa branche
  {sujet}   son sujet (nom court)                                  {port}     le port de son application
Un développeur ne peut donc agir que sur SA copie, SA branche, SA pile — jamais celles d'un autre, ni la branche
principale. Ex. : pousser = "git push origin {branche}" (aucun argument : impossible de viser une autre branche).

TOUTES ses commandes s'exécutent dans un bac à sable (_commandes.bac_a_sable) : elles lancent du code que le
développeur a pu modifier. Seuls les verbes « hors_bac » (git réseau : pousser, mettre à jour) en sortent, git y étant
lancé hooks et fsmonitor désactivés.
Réglages (config.toml, section [outils.<nom>]) : delai (secondes, 900 par défaut), lecture, actions, reseau (bool)."""
import importlib.util, os, re, shlex, subprocess
from pathlib import Path

_spec = importlib.util.spec_from_file_location("outil__commandes", Path(__file__).with_name("_commandes.py"))
_base = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_base)
CLES = ("copie", "branche", "sujet", "port")


class Outil(_base.Base):
    contexte = _base._contexte.ContexteDeLAppel({})                  # posé par le courtier pour CET appel

    def __init__(self, reglages, secret, verifier_hote):
        self.delai = int(reglages.get("delai", 900))
        self.masques = reglages.get("masques", []); self.reseau = bool(reglages.get("reseau")); self.hors_bac = set(); self.env_verbe = {}      # env_verbe : {verbe: variables en plus} (ex. l'auteur git de « mettre-a-jour »)
        super().__init__(reglages)

    def valeurs(self):
        """Lues dans l'agent.conf du demandeur (posé par le courtier dans self.contexte) — jamais fournies par l'agent."""
        conf = {}
        f = Path(self.contexte.get("dossier", "")) / "agent.conf"
        for l in (f.read_text().splitlines() if f.is_file() else []):
            if "=" in l and not l.lstrip().startswith("#"):
                k, v = l.split("=", 1); conf[k.strip()] = v.split("#")[0].strip()
        manque = [k for k in CLES if not conf.get(k)]
        if manque: raise PermissionError(f"cet outil est réservé aux développeurs d'équipe (manque : {', '.join(manque)})")
        conf["copie"] = os.path.expanduser(conf["copie"])
        if not re.fullmatch(r"[\w./-]+", conf["branche"]) or not conf["port"].isdigit(): raise PermissionError("agent.conf invalide")
        return {**{k: conf[k] for k in CLES}, **({"projet": conf["projet"]} if conf.get("projet") else {})}   # projet : facultatif (file des tests)

    def remplir(self, cmd):
        v = self.valeurs()
        for k in CLES: cmd = cmd.replace("{" + k + "}", shlex.quote(v[k]))
        return cmd, v

    def fabriquer_apercu(self, verbe, modele):
        def apercu(args):
            cmd, v = self.remplir(self.commande(modele, args)); return f"dans {v['copie']} : {cmd}"
        apercu.__doc__ = f"{verbe} : {modele}"
        return apercu

    def env_en_plus(self, verbe):
        """Les variables ajoutées pour CE verbe (env_verbe) ; equipe_dev y ajoute le verrou des suites tenu par le courtier."""
        return self.env_verbe.get(verbe, {})

    def executer(self, cmd, verbe=None, dossier=None):
        """`dossier` : jouer ailleurs que dans la copie de l'agent (copie FIGÉE d'un commit par le courtier : equipe_dev)."""
        if dossier: cmd = cmd.replace("{copie}", shlex.quote(str(dossier)))
        cmd, v = self.remplir(cmd); copie = Path(dossier or v["copie"])
        if not copie.is_dir(): raise RuntimeError(f"copie introuvable : {copie}")
        env = _base.env_lancement(dict(os.environ)); env.update(_base.ENV_GIT); env.update(self.env_en_plus(verbe))   # python3 = /usr/bin/python3 en tête, reste inchangé (_commandes.env_lancement)
        try:
            construire = None if verbe in self.hors_bac else (lambda args: _base.bac_a_sable(args, copie, self.masques, self.reseau))
            return _base._transport.executer_shell(cmd, construire=construire, cwd=copie, capture_output=True, text=True, timeout=self.delai, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"commande trop longue (plus de {self.delai} s) : arrêtée")
