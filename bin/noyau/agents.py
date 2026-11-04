"""Fichiers d'un agent : dossier, configuration, mémoire, checklist, journal.

Code déplacé de bin/berger (modulaire, lot 1) : aucun comportement changé."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.transport import *
from noyau.affichage import *
from noyau.conftexte import conf_texte      # lecteur d'agent.conf, partagé avec le courtier (outils/_portes.py)


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


def poser_accord_bypass(f):
    """L'accord du mode bypass (ACCORD_BYPASS) dans un .claude/settings.local.json ; rend None, ou le problème (le fichier est alors laissé tel quel).
    Installation du 04/11 (n° 141) : Berger pose ce fichier VIDE en 0444 (mcp-trous) et le propriétaire y a mis la clé à la main ; un write_text
    levait PermissionError et regenerer échouait pour tous. Vide vaut {} ; clé déjà vraie : rien d'écrit ; sinon la clé est FUSIONNÉE (les autres clés
    gardées) par un fichier temporaire du même dossier, au mode du fichier d'origine, puis os.replace. Jamais de chmod du fichier d'origine."""
    import stat
    u = os.umask(0o022); os.umask(u); mode = 0o666 & ~u   # fichier neuf : le mode d'un write_text (comme avant)
    r = {}
    if f.is_symlink(): return "est un lien : non suivi, laissé tel quel"
    if f.exists():
        try: texte = f.read_text()
        except (OSError, UnicodeDecodeError) as e: return f"illisible ({getattr(e, 'strerror', None) or e}) : laissé tel quel"
        try: r = json.loads(texte) if texte.strip() else {}
        except ValueError: return "n'est pas du JSON : laissé tel quel"
        if not isinstance(r, dict): return "n'est pas un objet JSON : laissé tel quel"
        if all(r.get(k) == v for k, v in ACCORD_BYPASS.items()): return None
        mode = stat.S_IMODE(f.stat().st_mode)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=".settings.local.", suffix=".tmp", dir=f.parent)
        with os.fdopen(fd, "w") as o: o.write(json.dumps({**r, **ACCORD_BYPASS}, ensure_ascii=False, indent=2) + "\n")
        os.chmod(tmp, mode); os.replace(tmp, f)
    except OSError as e:
        tmp and Path(tmp).unlink(missing_ok=True); return f"non écrit ({e.strerror or e}) : laissé tel quel"
    return None


__all__ = ('ECHANGES', '_STATUTS', 'agents', 'aujourdhui', 'poser_accord_bypass', 'cases', 'checklist', 'conf', 'conf_texte', 'dossier', 'ecritures_en_plus', 'externe', 'fichier_memoire', 'journal', 'lire', 'MEMOIRE_MAX', 'memoire_dossier', 'ouvert', 'pendants', 'signale_aujourdhui', 'superviseur', 'travail',)


MEMOIRE_MAX = 3000                                   # MEMORY.md de Berger ; une mémoire existante (index de fiches) n'a pas de limite


def journal(a, texte):
    d = dossier(a) / "memory"; d.mkdir(exist_ok=True)
    with open(d / f"{aujourdhui()}.md", "a") as f:
        f.write(f"- {datetime.datetime.now():%H:%M} — {texte}\n")
