#!/usr/bin/env python3
"""Journal des changements en fragments (spec docs/plans/2026-11-04-changelog-fragments-spec.md, lot C de
docs/plans/2026-11-04-acceleration-fusions-spec.md) : une branche écrit SA ligne dans `changelog.d/<sujet>.md`, jamais dans
CHANGELOG.md ; la branche de version les regroupe. Deux demandes n'ont donc plus de fichier commun.

Usage :
  python3 -I tests/changelog.py [verifier] [<racine>]                       code de retour = nombre de refus (joué par tests/suites.sh)
  python3 -I tests/changelog.py regrouper <x.y.z> <AAAA-MM-JJ> [<racine>]   écrit « ## [x.y.z] - date » et supprime les fragments

Un fragment : des titres `### Added|Changed|Deprecated|Removed|Fixed|Security` suivis de puces (Keep a Changelog 1.1.0, en
anglais), aucun titre `#`/`##`, nom en minuscules et tirets (`[a-z0-9-]+.md`), un seul niveau, fichier ordinaire non exécutable.

Transition : tant qu'aucune version n'a été regroupée, les lignes déjà écrites sous `## [Unreleased]` restent permises (les
demandes en cours finissent à l'ancienne, spec point 6) et `regrouper` les reprend en tête de la version. `regrouper` laisse
ensuite sous `[Unreleased]` la seule ligne REPERE : à partir de là, toute autre ligne sous `[Unreleased]` est refusée."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import datetime, os, re, stat, sys
from pathlib import Path

SECTIONS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")       # Keep a Changelog 1.1.0, dans cet ordre
NOM = re.compile(r"[a-z0-9-]+\.md")
REPERE = "<!-- Entries go in changelog.d/<topic>.md (see CONTRIBUTING.md): this section stays empty. -->"
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?")
TITRE = re.compile(r"###\s+(\S.*?)\s*")
NON_PUBLIE = re.compile(r"##\s*\[Unreleased\]\s*")


def sections(texte, ou):
    """Le texte d'un fragment → ({section: [lignes]}, [refus]). Chaque section garde ses lignes (puces et suites de puce)."""
    out, refus, courante = {}, [], None
    for n, ligne in enumerate(texte.splitlines(), 1):
        brut = ligne.rstrip()
        if re.match(r"#{1,2}(\s|$)", brut) or re.match(r"#{4,}", brut):
            refus.append(f"{ou}:{n} : titre « {brut[:40]} » interdit (seulement « ### <section> »)"); continue
        m = TITRE.fullmatch(brut)
        if m:
            if m.group(1) not in SECTIONS:
                refus.append(f"{ou}:{n} : section inconnue « {m.group(1)[:40]} » ({', '.join(SECTIONS)})"); courante = None; continue
            courante = m.group(1); out.setdefault(courante, []); continue
        if not brut: (out[courante].append("") if courante else None); continue
        if courante is None: refus.append(f"{ou}:{n} : ligne hors section (« ### Added » ou une autre avant les puces)"); continue
        out[courante].append(brut)
    for s in list(out):
        while out[s] and not out[s][-1]: out[s].pop()
        while out[s] and not out[s][0]: out[s].pop(0)
        if not out[s]: refus.append(f"{ou} : section « {s} » vide"); del out[s]
    return out, refus


def non_publie(journal):
    """(début, fin) des lignes du corps de `## [Unreleased]` (fin = le titre `## ` suivant), ou None."""
    lignes = journal.splitlines()
    for i, l in enumerate(lignes):
        if NON_PUBLIE.fullmatch(l.strip()):
            fin = next((j for j in range(i + 1, len(lignes)) if lignes[j].startswith("## ")), len(lignes))
            return i + 1, fin
    return None


def fragments(racine):
    """Les fragments de <racine>/changelog.d → ([(nom, texte)] triés par nom, [refus])."""
    d = racine / "changelog.d"; out, refus = [], []
    if os.path.islink(d): return [], ["changelog.d est un lien symbolique : refusé"]
    if not d.exists(): return [], []
    if not d.is_dir(): return [], ["changelog.d n'est pas un dossier"]
    for p in sorted(d.iterdir()):
        ou = f"changelog.d/{p.name}"; st = os.lstat(p)
        if stat.S_ISLNK(st.st_mode): refus.append(f"{ou} : lien symbolique refusé"); continue
        if stat.S_ISDIR(st.st_mode): refus.append(f"{ou} : sous-dossier refusé (un seul niveau)"); continue
        if not stat.S_ISREG(st.st_mode): refus.append(f"{ou} : pas un fichier ordinaire"); continue
        if st.st_mode & 0o111: refus.append(f"{ou} : fichier exécutable refusé"); continue
        if not NOM.fullmatch(p.name): refus.append(f"{ou} : nom refusé (minuscules, chiffres et tirets, puis .md)"); continue
        try: texte = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e: refus.append(f"{ou} : illisible ({e.__class__.__name__})"); continue
        if not texte.strip(): refus.append(f"{ou} : fragment vide"); continue
        out.append((p.name, texte))
    return out, refus


def verifier(racine):
    """→ (refus, fragments valides, lignes de transition sous [Unreleased])."""
    frags, refus = fragments(racine)
    valides = []
    for nom, texte in frags:
        secs, r = sections(texte, f"changelog.d/{nom}"); refus += r
        if not r and not secs: refus.append(f"changelog.d/{nom} : aucune section")
        if not r and secs: valides.append((nom, secs))
    try: journal = (racine / "CHANGELOG.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError): return refus + ["CHANGELOG.md absent ou illisible"], valides, []
    bornes = non_publie(journal)
    if bornes is None: return refus + ["CHANGELOG.md : pas de titre « ## [Unreleased] »"], valides, []
    corps = [l.rstrip() for l in journal.splitlines()[bornes[0]:bornes[1]]]
    utiles = [l for l in corps if l.strip() and l.strip() != REPERE]
    if REPERE in (l.strip() for l in corps):
        refus += [f"CHANGELOG.md : ligne sous [Unreleased] (« {l.strip()[:60]} ») : elle va dans changelog.d/<sujet>.md" for l in utiles]
        return refus, valides, []
    return refus, valides, corps


def regrouper(racine, version, date):
    """Écrit `## [version] - date` sous [Unreleased] (les lignes de transition d'abord, puis les fragments par nom, section par
    section dans l'ordre de Keep a Changelog), laisse le REPERE sous [Unreleased] et supprime les fragments. → message."""
    if not VERSION.fullmatch(version): raise ValueError(f"« {version} » n'est pas une version SemVer (x.y.z, sans « v »)")
    try: datetime.date.fromisoformat(date)
    except ValueError: raise ValueError(f"« {date} » n'est pas une date AAAA-MM-JJ")
    refus, valides, transition = verifier(racine)
    if refus: raise ValueError("fragments ou journal refusés, rien n'est regroupé :\n" + "\n".join(refus))
    journal = (racine / "CHANGELOG.md").read_text(encoding="utf-8")
    if re.search(r"(?m)^##\s*\[" + re.escape(version) + r"\]", journal): raise ValueError(f"la version {version} est déjà dans CHANGELOG.md")
    sources = []
    if any(l.strip() for l in transition):
        secs, r = sections("\n".join(transition), "CHANGELOG.md [Unreleased]")
        if r: raise ValueError("lignes de transition sous [Unreleased] mal formées :\n" + "\n".join(r))
        sources.append(secs)
    sources += [s for _, s in valides]
    if not sources: raise ValueError("rien à regrouper : ni fragment dans changelog.d/, ni ligne sous [Unreleased]")
    corps = []
    for s in SECTIONS:
        blocs = [x[s] for x in sources if s in x]
        if blocs: corps += [f"### {s}", ""] + [l for b in blocs for l in b] + [""]
    lignes = journal.splitlines(); debut, fin = non_publie(journal)
    nouveau = lignes[:debut] + ["", REPERE, "", f"## [{version}] - {date}", ""] + corps + lignes[fin:]
    (racine / "CHANGELOG.md").write_text("\n".join(nouveau).rstrip("\n") + "\n", encoding="utf-8")
    for nom, _ in valides: (racine / "changelog.d" / nom).unlink()
    try: (racine / "changelog.d").rmdir()
    except OSError: pass
    return f"ok regrouper : {len(valides)} fragment(s) regroupé(s) dans « ## [{version}] - {date} »" + (", lignes de transition reprises" if transition and any(l.strip() for l in transition) else "")


def main(argv):
    racine_defaut = Path(__file__).resolve().parent.parent
    if argv[:1] == ["regrouper"]:
        if len(argv) not in (3, 4): print("usage : changelog.py regrouper <x.y.z> <AAAA-MM-JJ> [<racine>]"); return 2
        try: print(regrouper(Path(argv[3]) if len(argv) == 4 else racine_defaut, argv[1], argv[2])); return 0
        except ValueError as e: print(f"ÉCHEC regrouper : {e}"); return 1
    if argv[:1] == ["verifier"]: argv = argv[1:]
    if len(argv) > 1 or (argv and argv[0].startswith("-")): print("usage : changelog.py [verifier] [<racine>]"); return 2
    refus, valides, transition = verifier(Path(argv[0]) if argv else racine_defaut)
    for r in refus: print(f"ÉCHEC {r}")
    if not refus:
        print(f"ok changelog : {len(valides)} fragment(s) valide(s)"
              + (", lignes de transition sous [Unreleased] (reprises au prochain regroupement)" if any(l.strip() for l in transition) else ""))
    return min(len(refus), 100)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
