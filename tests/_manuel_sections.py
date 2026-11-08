# -*- coding: utf-8 -*-
"""Empreintes du manuel PAR SECTION (lot D de docs/plans/2026-11-04-acceleration-fusions-spec.md, option (b)) : une empreinte
sha256 par section `## ` de docs/manuel.md, dans tests/attendus/manuel/<section>.sha256. Deux branches qui modifient deux
sections différentes ne touchent donc pas la même empreinte (tests/vitrine.py n'en contient plus aucune).

Une section = son titre `## …` et tout ce qui suit jusqu'au titre `## ` suivant (hors blocs de code) ; ce qui précède le premier
titre est la section « en-tete ». Le sommaire (`## Sommaire`) n'est pas figé : vitrine.py vérifie qu'il suit les titres.
Le nom d'une section : son titre en minuscules, sans accents, chaque suite de signes devenue « - »."""
import hashlib, re, unicodedata
from pathlib import Path

MANUEL = "docs/manuel.md"
ATTENDUS = "tests/attendus/manuel"
SOMMAIRE = "Sommaire"
RECALCUL = "python3 -I tests/manuel-empreintes.py recalculer"


def nom(titre):
    a = unicodedata.normalize("NFKD", titre).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", a).strip("-") or "sans-titre"


def sections(texte):
    """→ [(titre, nom, texte de la section)] dans l'ordre du manuel, sans le sommaire."""
    out, titre, lignes, code = [], "(en-tête)", [], False
    for l in texte.splitlines(keepends=True):
        if l.startswith("```"): code = not code
        if not code and l.startswith("## "):
            out.append((titre, lignes)); titre, lignes = l[3:].strip(), []
        lignes.append(l)
    out.append((titre, lignes))
    return [(t, "en-tete" if t == "(en-tête)" else nom(t), "".join(c)) for t, c in out if t != SOMMAIRE]


def empreinte(texte):
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def verifier(racine):
    """→ (refus nommés, nombre de sections). Section modifiée sans recalcul, ajoutée, retirée, ou deux titres au même nom."""
    racine = Path(racine); d = racine / ATTENDUS
    try: secs = sections((racine / MANUEL).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e: return [f"{MANUEL} illisible ({e.__class__.__name__})"], 0
    refus, vus = [], {}
    for titre, n, texte in secs:
        if n in vus: refus.append(f"deux sections au même nom « {n} » (« {vus[n]} » et « {titre} ») : renomme l'une d'elles"); continue
        vus[n] = titre
        f = d / f"{n}.sha256"
        if not f.is_file():
            refus.append(f"section ajoutée « {titre} » : empreinte absente ({ATTENDUS}/{n}.sha256) — {RECALCUL} {n}")
        elif f.read_text().split()[:1] != [empreinte(texte)]:
            refus.append(f"section « {titre} » modifiée sans recalcul de son empreinte ({ATTENDUS}/{n}.sha256) — {RECALCUL} {n}")
    for f in sorted(d.glob("*.sha256")) if d.is_dir() else []:
        if f.stem not in vus:
            refus.append(f"section retirée « {f.stem} » : {ATTENDUS}/{f.name} n'a plus de section — {RECALCUL} {f.stem} (le supprime)")
    return refus, len(secs)


def recalculer(racine, noms=()):
    """Écrit l'empreinte des sections `noms` (toutes si vide) ; un nom sans section supprime son empreinte. → [ce qui est fait]."""
    racine = Path(racine); d = racine / ATTENDUS; d.mkdir(parents=True, exist_ok=True)
    secs = {n: (t, x) for t, n, x in sections((racine / MANUEL).read_text(encoding="utf-8"))}
    cibles = list(noms) or list(secs) + [f.stem for f in d.glob("*.sha256") if f.stem not in secs]
    fait = []
    for n in cibles:
        if not re.fullmatch(r"[a-z0-9-]+", n): raise ValueError(f"nom de section refusé : « {n} »")
        f = d / f"{n}.sha256"
        if n in secs: f.write_text(empreinte(secs[n][1]) + "\n"); fait.append(f"{n} : empreinte écrite")
        elif f.exists(): f.unlink(); fait.append(f"{n} : section retirée, empreinte supprimée")
        else: raise ValueError(f"aucune section « {n} » dans {MANUEL}")
    return fait
