"""Constantes et configuration de l'installation (config.toml, chemins, programmes externes). Lu une fois, avant tout.

Code déplacé de bin/berger (modulaire, lot 1) : aucun comportement changé."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path


HOME = Path.home()
BERGER = Path(os.environ.get("BERGER_DIR") or Path(__file__).resolve().parent.parent.parent)   # le dossier de l'installation
AGENTS = BERGER / "agents"
COMMUN = BERGER / "commun"
CODEX_HOME = BERGER / ".codex"
PATH_MISE = f"{HOME}/.local/share/mise/shims:{HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin"
os.environ["PATH"] = PATH_MISE + ":" + os.environ.get("PATH", "")
# Programmes externes remplaçables (tests : faux Herdr, pas de notification de bureau). Le PATH ci-dessus place mise en
# tête : un faux Herdr mis dans le PATH ne serait JAMAIS pris (vécu le 05/10 : un test a ouvert un vrai agent).
HERDR = os.environ.get("BERGER_HERDR", "herdr"); NOTIFY_SEND = os.environ.get("BERGER_NOTIFY_SEND", "notify-send")

# Tout ce qui est PROPRE à une installation (nom, coffre, dossiers à protéger, garde-fous, outils) est dans
# config.toml, jamais versionné ; le dépôt ne contient que config.exemple.toml.
try:
    CONFIG = tomllib.loads((BERGER / "config.toml").read_text())
except FileNotFoundError:
    sys.exit(f"config.toml absent : copier {BERGER}/config.exemple.toml en {BERGER}/config.toml et l'adapter.")
PROPRIETAIRE = CONFIG.get("proprietaire", "l'utilisateur")
ESPACE_BERGER = f"{CONFIG.get('icone_berger', '')} Berger".strip()       # nom de l'espace de pilotage dans Herdr
if CONFIG.get("fuseau"): os.environ["TZ"] = CONFIG["fuseau"]; time.tzset()
COFFRE_DEFAUT = "~/.config/berger/coffre.json"                           # valeur du produit (aussi dans le courtier et l'exemple)
COFFRE = Path(os.path.expanduser(CONFIG.get("coffre", COFFRE_DEFAUT)))

# Emplacements illisibles pour TOUS les agents, sur les deux moteurs (mesuré le 03/10/2026).
# Codex : un SEUL fichier masquable (deux = « bwrap: Bad file descriptor ») et un chemin absent bloque le démarrage.
MASQUES_DOSSIERS = list(CONFIG.get("masques", []))
MASQUES_OPTIONNELS = list(CONFIG.get("masques_si_presents", []))          # ajoutés seulement s'ils existent
# Identifiants de Codex : au trousseau système (défaut) ; « fichier » pour une machine sans trousseau (serveur) — le
# dossier du profil Codex des agents (qui contient alors auth.json) devient ILLISIBLE à tous les agents.
CODEX_FICHIER = CONFIG.get("codex_identifiants", "trousseau") == "fichier"
if CODEX_FICHIER: MASQUES_DOSSIERS.append(str(CODEX_HOME.relative_to(HOME)))
MASQUE_FICHIER = CONFIG.get("masque_fichier", ".claude/.credentials.json")
RESULTATS = BERGER / "courtier/panneaux"                                 # résultats des sources, écrits par le courtier
# Bibliothèque (08/10/2026, lot 2) : un dossier de travail par agent INSCRIT (`bibliotheque = oui` dans agent.conf), masqué
# aux autres, et un dossier commun que le propriétaire remplit et que les agents lisent sans jamais l'écrire. DANS ~/berger
# par défaut : non versionnée (liste blanche du .gitignore) mais prise par `berger sauvegarder`.
BIBLIOTHEQUE = Path(os.path.expanduser((CONFIG.get("bibliotheque") or {}).get("racine", ""))) if (CONFIG.get("bibliotheque") or {}).get("racine") else BERGER / "bibliotheque"
BIBLIO_COMMUN = BIBLIOTHEQUE / "commun"
BIBLIO_EQUIPES = BIBLIOTHEQUE / "equipes"   # lot 4 : <équipe>/projets/<projet>/ (membres seuls) et <équipe>/archives/ (fermés)

GARDES = [dict(g, commande=os.path.expanduser(g["commande"]).replace("~/", f"{HOME}/")) for g in CONFIG.get("gardes", [])]




__all__ = ('AGENTS', 'BERGER', 'BIBLIOTHEQUE', 'BIBLIO_COMMUN', 'BIBLIO_EQUIPES', 'CODEX_FICHIER', 'CODEX_HOME', 'COFFRE', 'COFFRE_DEFAUT', 'COMMUN', 'CONFIG', 'ESPACE_BERGER', 'GARDES', 'HERDR', 'HOME', 'MASQUES_DOSSIERS', 'MASQUES_OPTIONNELS', 'MASQUE_FICHIER', 'NOTIFY_SEND', 'PATH_MISE', 'PROPRIETAIRE', 'RESULTATS',)
