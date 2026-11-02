"""Affichage : couleurs ANSI, largeur, découpe, titres et cartes des panneaux.

Code déplacé de bin/berger (modulaire, lot 1) : aucun comportement changé."""
import datetime, json, os, re, shlex, shutil, subprocess, sys, tempfile, time, tomllib, unicodedata
import importlib.util
import shutil as _sh, textwrap
from pathlib import Path
from noyau.config import *
from noyau.transport import *


R, GRAS, PALE = "\033[0m", "\033[1m", "\033[2m"


BLEU, JAUNE, VERT, ROUGE, CYAN, INV = "\033[34m", "\033[33m", "\033[32m", "\033[31m", "\033[36m", "\033[7m"


STATUTS = {"idle": ("au repos", PALE + VERT), "done": ("a fini", VERT), "working": ("travaille", BLEU + GRAS),
           "blocked": ("attend une réponse", JAUNE + GRAS), "unknown": ("pas d'agent", PALE), "?": ("?", PALE)}


ANSI = re.compile(r"\033\[[0-9;?]*[A-Za-z]")


def _l(ch):  # largeur d'un caractère à l'écran
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else (0 if unicodedata.combining(ch) else 1)


def vlen(t): return sum(_l(ch) for ch in ANSI.sub("", t))


def couper(t, w):
    """Tronque à w colonnes visibles en gardant les codes couleur ; ajoute … si coupé."""
    if vlen(t) <= w: return t
    out, n, i = "", 0, 0
    while i < len(t):
        m = ANSI.match(t, i)
        if m: out += m.group(); i = m.end(); continue
        if n + _l(t[i]) > w - 1: break
        out += t[i]; n += _l(t[i]); i += 1
    return out + "…" + R


def pad(t, w): t = couper(t, w); return t + " " * (w - vlen(t))


def plat(t):
    """Markdown → texte lisible : sans **, `, ni balises."""
    return re.sub(r"\*\*|`|__", "", t).strip()


def plier(t, w, debut="", suite=None, style=""):
    """Plie un texte en lignes de w colonnes, avec un préfixe pour la 1re ligne et un retrait pour les suivantes."""
    suite = " " * vlen(debut) if suite is None else suite
    lignes = textwrap.wrap(t, max(10, w - vlen(debut))) or [""]
    return [(debut if i == 0 else suite) + style + l + (R if style else "") for i, l in enumerate(lignes)]


def entete(c, vue, w, droite=""):
    gauche = f" {c['icone']}  {c['nom'].upper()}  ·  {vue}"
    droite = f"{droite}  {datetime.datetime.now():%H:%M} "
    return INV + GRAS + gauche + " " * max(1, w - vlen(gauche) - vlen(droite)) + droite + R


def titre_section(t, couleur, w): return [couleur + GRAS + t + R, couleur + PALE + "─" * min(w, max(vlen(t), 12)) + R]


def statuts_texte(statuts):
    """Les statuts d'un agent (données Statut) en texte de panneau : « claude au repos   codex travaille »."""
    out = []
    for s in statuts:
        lib, col = STATUTS.get(s["etat"], ("?", PALE))
        out.append(f"{PALE}{s['moteur']}{R} {col}{lib}{R}")
    return "   ".join(out)


def jauge(f, t, w=16, col=BLEU):
    n = w * f // t if t else 0
    return col + "━" * n + R + PALE + "━" * (w - n) + R


def date_fin(lib):
    """« Texte  (ajouté 2026-10-04) » → ("Texte", "04/10")."""
    m = re.search(r"\((?:ajouté|fait)\s+(\d{4})-(\d\d)-(\d\d)\)\s*$", lib)
    return (lib[:m.start()].strip(), f"{m.group(3)}/{m.group(2)}") if m else (lib.strip(), "")


def colonnes_tableau_texte(dt_, w):
    """Les 4 colonnes du Tableau de l'agent en texte de panneau, pliées à la largeur w : depuis tableau_donnees()."""
    ck = dt_["en_cours"]
    cols = []
    # ▶ EN COURS
    l = []
    if ck:
        l += plier(plat(ck["titre"]), w, style=GRAS)
        l.append(f"{jauge(ck['faites'], ck['total'], min(16, w - 6))} {ck['faites']}/{ck['total']}")
        for e in ck["etapes"]:
            lib = plat(e["libelle"].replace("← en cours", ""))
            if e["fait"]: l += plier(lib, w, PALE + "✓ ", PALE + "  ", PALE)
            elif lib == plat(ck["en_cours"]): l += plier(lib, w, BLEU + GRAS + "▸ " + R, "  ", GRAS)
            else: l += plier(lib, w, "○ ", "  ")
        if ck["bloque"]: l += [""] + plier(plat(ck["bloque"]), w, JAUNE + GRAS + "! Bloqué : " + R, "  ", JAUNE)
    else:
        l.append(PALE + "rien en cours" + R)
    cols.append(("▶ EN COURS", BLEU, l))
    # ! ATTEND LE PROPRIÉTAIRE
    l = []
    for x in dt_["attend"]:
        if x["genre"] == "bloque": l += plier(plat(x["texte"]), w, JAUNE + "! " + R, "  ")
        elif x["genre"] == "validation":
            n = "?" if x["n"] is None else x["n"]
            l += plier(f"écriture n° {n} : {x['texte']}", w, JAUNE + "✎ " + R, "  ")
        elif x["genre"] == "proposition": l += plier(f"valider ou refuser : {x['texte']}", w, JAUNE + "? " + R, "  ")
        else: l += plier(plat(x["texte"]), w, JAUNE + "♥ " + R, "  ")
    cols.append((f"! ATTEND {PROPRIETAIRE.upper()} ({len(dt_['attend'])})", JAUNE, l or [PALE + "rien" + R]))
    # ○ À FAIRE
    l = []
    for x in dt_["a_faire"]: l += plier(x["libelle"] + (f"  {PALE}{x['date']}{R}" if x["date"] else ""), w, "○ ", "  ")
    cols.append(("○ À FAIRE", CYAN, l or [PALE + "rien" + R]))
    # ✓ FAIT
    l = []
    for x in dt_["fait"]: l += plier(x["libelle"] + (f"  {x['date']}" if x["date"] else ""), w, VERT + "✓ " + R, "  ", PALE)
    for x in dt_["historique"]: l += plier(f"{plat(x['titre'])}  {x['date']}", w, VERT + "✓ " + R, "  ", PALE)
    cols.append(("✓ FAIT", VERT, l or [PALE + "rien" + R]))
    return cols


def puces(bloc):
    """Puces « - **Titre** : texte » ou « - texte » d'une section markdown → [(titre, texte)]."""
    out = []
    for m in re.finditer(r"^(?:-|\d+\.) (?:\*\*(.+?)\*\*\s*:?\s*)?(.+?)(?=^(?:-|\d+\.) |\n\n|\Z)", bloc, re.M | re.S):
        out.append((plat(m.group(1) or ""), plat(" ".join(m.group(2).split()))))
    return out


def section(md, titre):
    m = re.search(r"^## " + titre + r"[^\n]*\n(.*?)(?=^## |\Z)", md, re.M | re.S | re.I)
    return m.group(1) if m else ""


def mini_entete(c, rubrique, w):
    g = f" {c['icone']}  {c['nom']}  ·  {rubrique}"
    return INV + GRAS + g + " " * max(1, w - vlen(g)) + R


def prochaine(quand):
    """« lundi 08:30 » / « tous-les-jours 07:00 » → texte de la prochaine exécution."""
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    m = re.match(r"(\S+)\s+(\d\d):(\d\d)", quand or "")
    if not m: return "manuelle"
    now = datetime.datetime.now()
    for k in range(8):
        jour = now + datetime.timedelta(days=k)
        if m.group(1) in ("tous-les-jours", jours[jour.weekday()]):
            t = jour.replace(hour=int(m.group(2)), minute=int(m.group(3)), second=0, microsecond=0)
            if t > now: return ("aujourd'hui" if k == 0 else "demain" if k == 1 else jours[t.weekday()]) + f" {t:%H:%M}"
    return "?"


__all__ = ('ANSI', 'BLEU', 'CYAN', 'GRAS', 'INV', 'JAUNE', 'PALE', 'R', 'ROUGE', 'STATUTS', 'VERT', '_l', 'colonnes_tableau_texte', 'couper', 'date_fin', 'entete', 'jauge', 'mini_entete', 'pad', 'plat', 'plier', 'prochaine', 'puces', 'section', 'statuts_texte', 'titre_section', 'vlen',)
