"""Fichiers d'un agent : dossier, configuration, mémoire, checklist, journal.

Code déplacé de bin/berger (modulaire, lot 1) : aucun comportement changé."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.transport import *
from noyau.affichage import *


def agents():
    return sorted(p.name for p in AGENTS.iterdir() if (p / "agent.conf").is_file()) if AGENTS.is_dir() else []


def dossier(a):
    d = AGENTS / a
    if not (d / "agent.conf").is_file():
        sys.exit(f"agent inconnu : {a} (agents : {', '.join(agents()) or 'aucun'})")
    return d


def conf(a):
    c = {"nom": a.capitalize(), "moteur": "codex", "panneaux": "codex", "heures": "8-19", "icone": "●",
         # mur = strict (bac à sable, ni réseau ni coffre : accès par le courtier) | ouvert (comme un agent classique :
         # réseau, SSH, coffre, garde-fous seulement — pour migrer des agents qui en ont besoin, 04/10/2026)
         "mur": "strict", "rc": "", "dossier": "", "fiche": "grille", "domaine": "", "consigne_fichier": "",
         # memoire = dossier d'une mémoire EXISTANTE (index MEMORY.md + une fiche par fait) : Berger s'y branche au lieu
         # d'ouvrir une seconde mémoire (pas de doublon, 04/10/2026)
         "memoire": "",
         # développeur d'équipe (posés par berger equipe ouvrir) : projet, sujet, copie, branche, port
         "projet": "", "sujet": "", "copie": "", "branche": "", "port": "",
         # ecrire_aussi = dossiers (séparés par des virgules) où un agent STRICT peut écrire en plus du sien (ex. livrables)
         "ecrire_aussi": "",
         # lecture_seule = oui : le courtier refuse toute écriture (même validée), mission, délégation et décision (agent de mission)
         "lecture_seule": "",
         # superviseur = oui : LIT les dossiers des autres agents, leurs dossiers de bibliothèque et les projets (le gardien
         # de Berger) — sans jamais y écrire ; le coffre, les clés et les sources des outils restent masqués (09/10/2026)
         "superviseur": ""}
    return {**c, **conf_texte((AGENTS / a / "agent.conf").read_text())}


def conf_texte(texte):
    """Les réglages `cle = valeur` d'un texte d'agent.conf (`#` = commentaire), sans les défauts."""
    c = {}
    for ligne in texte.splitlines():
        if "=" in ligne and not ligne.lstrip().startswith("#"):
            k, v = ligne.split("=", 1); c[k.strip()] = v.split("#")[0].strip()
    return c


def travail(a):
    """Dossier de TRAVAIL du moteur : celui de l'agent, ou un dossier existant (`dossier =`, ex. un rôle déjà en place
    dont des scripts dépendent). Les fichiers de Berger (mémoire, journal, TODO…) restent dans agents/<agent>/."""
    d = conf(a).get("dossier")
    return Path(os.path.expanduser(d)) if d else dossier(a)


def externe(a): return travail(a) != dossier(a)


def memoire_dossier(a):
    """Dossier de mémoire (index MEMORY.md + une fiche par fait). Chemin relatif = DANS le dossier Berger de l'agent
    (format neutre, ex. `memoire = memoire`) ; absolu = une mémoire existante ailleurs."""
    m = conf(a).get("memoire")
    if not m: return None
    m = Path(os.path.expanduser(m))
    return m if m.is_absolute() else dossier(a) / m


def ecritures_en_plus(a):
    return [str(Path(os.path.expanduser(x.strip()))) for x in conf(a).get("ecrire_aussi", "").split(",") if x.strip()]


def fichier_memoire(a):
    """Le fichier lu pour la mémoire longue : MEMORY.md de Berger, ou l'index de la mémoire existante."""
    m = memoire_dossier(a)
    return (m / "MEMORY.md") if m else (dossier(a) / "MEMORY.md")


def ouvert(a): return conf(a).get("mur") == "ouvert"


def superviseur(a): return conf(a).get("superviseur", "").lower() in ("oui", "yes", "true", "1")


def lire(p, defaut=""):
    try: return Path(p).read_text()
    except OSError: return defaut


def aujourdhui(): return datetime.date.today().isoformat()


ECHANGES = BERGER / "courtier/echanges.jsonl"


def cases(texte):
    """Lignes « - [ ] » / « - [x] » d'un fichier markdown → [(fait, libellé)]."""
    return [(m.group(1).lower() == "x", m.group(2).strip())
            for m in re.finditer(r"^\s*-\s*\[( |x|X)\]\s*(.+)$", texte, re.M)]


def checklist(a):
    t = lire(dossier(a) / "CHECKLIST.md").strip()
    if not t: return None
    titre = next((l[1:].strip() for l in t.splitlines() if l.startswith("#")), "travail en cours")
    c = cases(t)
    ligne_bloque = next((l.strip() for l in t.splitlines() if l.lstrip().startswith("⚠")), "")
    bloque = ligne_bloque.split(":", 1)[-1].strip() if ligne_bloque else ""
    en_cours = next((lib.replace("← en cours", "").strip() for fait, lib in c if not fait), "")
    fini = bool(re.search(r"^(Terminé|Abandonné)", t, re.M))
    # marquages pour le propriétaire (spec interface §6.3) : « ⚠ Go attendu : … » reste un blocage (supervision inchangée),
    # mais c'est un go qu'il attend ; « ❓ Question : … » est une question qui lui est posée (Claude ou Codex)
    question = next((l.split(":", 1)[-1].strip() for l in t.splitlines() if l.lstrip().startswith("❓") and ":" in l), "")
    return {"titre": titre, "faites": sum(f for f, _ in c), "total": len(c), "en_cours": en_cours,
            "bloque": bloque, "fini": fini, "etapes": c, "go": bool(re.match(r"⚠\s*Go attendu", ligne_bloque, re.I)), "question": question}


def pendants(a):
    return sorted(p.name for p in (dossier(a) / "pending").glob("*.md"))


def signale_aujourdhui(a):
    t = lire(dossier(a) / "heartbeat" / f"{aujourdhui()}.md")
    return [l.strip() for l in t.splitlines() if l.startswith("    ")]


_STATUTS = {}


__all__ = ('ECHANGES', '_STATUTS', 'agents', 'aujourdhui', 'cases', 'checklist', 'conf', 'conf_texte', 'dossier', 'ecritures_en_plus', 'externe', 'fichier_memoire', 'journal', 'lire', 'MEMOIRE_MAX', 'memoire_dossier', 'ouvert', 'pendants', 'signale_aujourdhui', 'superviseur', 'travail',)


MEMOIRE_MAX = 3000                                   # MEMORY.md de Berger ; une mémoire existante (index de fiches) n'a pas de limite


def journal(a, texte):
    d = dossier(a) / "memory"; d.mkdir(exist_ok=True)
    with open(d / f"{aujourdhui()}.md", "a") as f:
        f.write(f"- {datetime.datetime.now():%H:%M} — {texte}\n")
