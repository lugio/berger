# -*- coding: utf-8 -*-
"""Projets d'équipe de la bibliothèque (lot 4, 08/10/2026) — outil « projet » du courtier, créé d'office s'il y a des équipes.

- ouvrir <équipe> <projet> <membre,membre…> / fermer <équipe> <projet> : ÉCRITURES, demandées par le chef de projet ou le
  coordinateur de l'équipe, soumises à validation (`projet_par` de [equipes.<équipe>] : "proprietaire" par défaut,
  "coordinateur" ou "chef_projet") ; exécutées par `berger projet …` (hors bac à sable : dossier, registre, réglages).
- partager <équipe> <projet> <fichier> : copie un fichier de MON dossier de travail vers un projet dont je suis membre ;
  refusé s'il contient une valeur du coffre ou une forme connue de clé (même filtre que les réponses du courtier).
- liste [<équipe>] : les projets ouverts et leurs membres.
Le registre des membres vit hors de la bibliothèque (equipes/<équipe>/projets.json de l'installation) : un membre ne peut ni
s'y ajouter quelqu'un, ni lever les droits."""
import importlib.util, datetime, json, os, re, stat, subprocess
from pathlib import Path

import importlib.util
_spec_transport = importlib.util.spec_from_file_location('berger_transport', Path(__file__).with_name('_transport.py'))
_transport = importlib.util.module_from_spec(_spec_transport); _spec_transport.loader.exec_module(_transport)

_spec = importlib.util.spec_from_file_location("outil__contexte", Path(__file__).with_name("_contexte.py"))
_contexte = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_contexte)   # contexte propre à chaque appel

MAX_OCTETS = 10 * 1024 * 1024


class Outil:
    contexte = _contexte.ContexteDeLAppel({})                        # posé par le courtier pour CET appel

    def __init__(self, reglages, secret, verifier_hote):
        self.berger = Path(reglages["berger"]); self.racine = Path(reglages["racine"]); self.equipes = reglages.get("equipes", {})
        self.proprietaire = reglages.get("proprietaire", "le propriétaire")
        self.filtre_fuite = lambda texte: True    # remplacé par le courtier ; tant qu'il ne l'est pas, tout partage est refusé
        self.verbes = {"liste": self.liste, "partager": self.partager}
        self.ecritures = {"ouvrir": (self.apercu_ouvrir, self.ouvrir), "fermer": (self.apercu_fermer, self.fermer)}

    def hotes(self): return {}

    # ── outils communs ──
    def _equipe(self, eq):
        if eq not in self.equipes: raise ValueError(f"équipe inconnue : {eq}")
        return self.equipes[eq]

    def _registre(self, eq):
        try: return json.loads((self.berger / "equipes" / eq / "projets.json").read_text())
        except (OSError, ValueError): return {}

    def _pilote(self, eq):
        e = self._equipe(eq); a = self.contexte.get("agent")
        if a not in (e.get("chef_projet"), e.get("coordinateur")):
            raise PermissionError(f"{a} n'est ni le chef de projet ni le coordinateur de l'équipe {eq}")
        return a

    def valideur(self, verbe, args):
        """Qui décide : le propriétaire (défaut), ou l'agent désigné par `projet_par` — jamais le demandeur (le courtier y veille)."""
        e = self.equipes.get(args[0] if args else "", {}); qui = e.get("projet_par", "proprietaire")
        return e.get(qui) if qui in ("coordinateur", "chef_projet") else None

    def _berger(self, *args):
        r = _transport.executer(str(self.berger / "bin/berger"), ['projet', *args], capture_output=True, text=True, timeout=300)
        if r.returncode: raise RuntimeError((r.stderr or r.stdout).strip()[-300:])
        return r.stdout.strip()

    # ── écritures (validées) ──
    def apercu_ouvrir(self, args):
        """ouvrir <équipe> <projet> <membre,membre…> : dossier partagé, membres seuls"""
        if len(args) != 3: raise ValueError("projet ouvrir <équipe> <projet> <membre,membre…>")
        self._pilote(args[0])
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,39}", args[1]): raise ValueError("projet : 2 à 40 caractères, minuscules, chiffres et tirets")
        if args[1] in self._registre(args[0]): raise ValueError(f"le projet {args[1]} est déjà ouvert")
        return f"ouvrir le projet {args[0]}/{args[1]} (dossier partagé de la bibliothèque) pour : {args[2]}"

    def ouvrir(self, args):
        par = self.contexte.get("agent") or self.proprietaire
        return self._berger("ouvrir", args[0], args[1], args[2], "--par", par)

    def apercu_fermer(self, args):
        """fermer <équipe> <projet> : archivé (rien supprimé), droits retirés"""
        if len(args) != 2: raise ValueError("projet fermer <équipe> <projet>")
        self._pilote(args[0])
        if args[1] not in self._registre(args[0]): raise ValueError(f"pas de projet ouvert {args[0]}/{args[1]}")
        return f"fermer le projet {args[0]}/{args[1]} : dossier archivé (rien supprimé), droits des membres retirés"

    def fermer(self, args):
        par = self.contexte.get("agent") or self.proprietaire
        return self._berger("fermer", args[0], args[1], "--par", par)

    # ── lecture et partage ──
    def liste(self, args):
        """liste [<équipe>] : projets ouverts et membres"""
        eqs = [args[0]] if args else list(self.equipes)
        for eq in eqs: self._equipe(eq)
        return {eq: {p: v.get("membres", []) for p, v in self._registre(eq).items()} for eq in eqs}

    def partager(self, args):
        """partager <équipe> <projet> <fichier> : copie un fichier de TON dossier de travail dans un projet dont tu es membre"""
        if len(args) != 3: raise ValueError("projet partager <équipe> <projet> <fichier de ton dossier de travail>")
        eq, p, nom = args; a = self.contexte.get("agent", "")
        v = self._registre(eq).get(p) if eq in self.equipes else None
        if not v: raise ValueError(f"pas de projet ouvert {eq}/{p}")
        if a not in v.get("membres", []): raise PermissionError(f"{a} n'est pas membre du projet {eq}/{p}")
        # Le courtier tourne HORS bac à sable et l'agent écrit dans son travail/ : entre une vérification et une lecture, il
        # pourrait remplacer le fichier (ou un dossier du chemin) par un lien vers le coffre (relecture du 08/10, TOCTOU).
        # Donc : chaque composant ouvert SANS suivre de lien, depuis le dossier précédent (dir_fd), la source ouverte UNE
        # fois, fstat (fichier ordinaire, taille), lue UNE fois en mémoire ; c'est CE contenu qui est filtré puis écrit.
        parties = [x for x in nom.split("/") if x]
        if not parties or any(x in (".", "..") for x in parties): raise PermissionError("le fichier doit être dans ton dossier de travail")
        sans_lien = os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        fds = []
        try:
            try: fds.append(os.open(self.racine / "agents" / a / "travail", os.O_RDONLY | os.O_DIRECTORY | sans_lien))
            except OSError: raise PermissionError(f"{a} n'a pas de dossier de travail dans la bibliothèque (bibliotheque = oui)")
            try:
                for x in parties[:-1]: fds.append(os.open(x, os.O_RDONLY | os.O_DIRECTORY | sans_lien, dir_fd=fds[-1]))
                # O_NONBLOCK : un tube (FIFO) posé à la place du fichier ne bloque pas le courtier à l'ouverture (refusé par S_ISREG)
                fds.append(os.open(parties[-1], os.O_RDONLY | os.O_NONBLOCK | sans_lien, dir_fd=fds[-1]))
            except OSError: raise PermissionError(f"fichier introuvable, ou lien refusé, dans ton dossier de travail : {nom}")
            st = os.fstat(fds[-1])
            if not stat.S_ISREG(st.st_mode): raise PermissionError(f"pas un fichier ordinaire : {nom}")
            if st.st_size > MAX_OCTETS: raise ValueError(f"fichier trop gros (plus de {MAX_OCTETS // 1048576} Mo)")
            with os.fdopen(os.dup(fds[-1]), "rb") as f: contenu = f.read(MAX_OCTETS + 1)
        finally:
            for fd in fds: os.close(fd)
        if len(contenu) > MAX_OCTETS: raise ValueError(f"fichier trop gros (plus de {MAX_OCTETS // 1048576} Mo)")
        if self.filtre_fuite(contenu.decode("utf-8", errors="ignore")):
            raise PermissionError("partage refusé : le fichier contient un secret (valeur du coffre ou forme connue de clé)")
        # Destination : le dossier du projet ouvert sans suivre de lien, puis création EXCLUSIVE sans suivre de lien (un membre
        # pourrait y avoir posé un lien, même cassé, au nom du fichier) ; nom horodaté si pris.
        try: dd = os.open(self.racine / "equipes" / eq / "projets" / p, os.O_RDONLY | os.O_DIRECTORY | sans_lien)
        except OSError: raise RuntimeError(f"dossier du projet {eq}/{p} absent ou remplacé")
        base = Path(parties[-1])
        try:
            for nom_dest in (base.name, f"{base.stem}-{datetime.datetime.now():%Y%m%d-%H%M%S}{base.suffix}"):
                try: fd = os.open(nom_dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | sans_lien, 0o664, dir_fd=dd)
                except FileExistsError: continue
                with os.fdopen(fd, "wb") as f: f.write(contenu)
                return f"copié dans le projet {eq}/{p} : {nom_dest}"
        finally: os.close(dd)
        raise RuntimeError("un fichier de ce nom existe déjà dans le projet : renomme-le et recommence")
