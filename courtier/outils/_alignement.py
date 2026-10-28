# -*- coding: utf-8 -*-
"""Alignement après une mise en production (spec docs/plans/2026-10-16-alignement-spec.md) — pas un type d'outil en soi.

Ce qu'un projet déclare dans `[equipes.<p>]` (jamais dans le code) : `alignement` (les éléments à tenir après une mise en
production), `prod_outil` (l'ACTION dont le compte rendu « ok » ouvre la liste), `compte_rendu_outil` et
`version_servie_outil` (des LECTURES), `wiki` (l'arborescence du projet au wiki) et `[equipes.<p>.modules]`. Une
déclaration fautive arrête le courtier au chargement (comme `installer_outil`) ; un projet sans ces lignes : rien ne change."""
import re

ELEMENTS = ("changelog", "wiki", "memoire", "skills", "versions")
RELIRE = ("wiki:", "skill:", "memoire:")
MODULE = re.compile(r"[A-Za-z0-9][\w-]{0,39}")
CLES = ("alignement", "prod_outil", "compte_rendu_outil", "version_servie_outil", "wiki", "modules")
OUTILS_WIKI = {"lecture": "wikijs-lecture", "ecriture": "wikijs-ecriture"}   # [wiki] lecture / ecriture de config.toml : autres noms


def outils_wiki(config):
    """{"lecture": <outil>, "ecriture": <outil>} : les outils du wiki de l'installation ([wiki] de config.toml, sinon ceux-ci)."""
    w = config.get("wiki") if isinstance(config.get("wiki"), dict) else {}
    return {k: str(w.get(k) or v) for k, v in OUTILS_WIKI.items()}


def chemin_wiki(c):
    """Un chemin du wiki ramené à sa forme simple (sans « / » autour) ; None s'il est vide ou contient « .. »."""
    c = str(c or "").strip().strip("/")
    return c if c and ".." not in c and "//" not in c and not re.search(r"\s", c) else None


def dans_zone(chemin, zone):
    """`chemin` est `zone` ou en dessous (« docs/x » est dans « docs/ », pas dans « doc »)."""
    z = str(zone).strip().strip("/")
    return bool(z) and (chemin == z or chemin.startswith(z + "/"))


def controler(p, e, lectures, actions, zones):
    """Refus au chargement du courtier. `lectures` / `actions` : {outil: {verbes}} ; `zones` : les zones de l'outil wiki de
    lecture (None : outil ou zones introuvables). → la liste des motifs de refus (vide : déclaration acceptée)."""
    refus = []
    def verbe(cle):
        outil, _, v = str(e.get(cle) or "").partition(" ")
        return outil, v.strip()
    al = e.get("alignement", [])
    if not isinstance(al, list) or any(x not in ELEMENTS for x in al):
        inconnus = [str(x) for x in al if x not in ELEMENTS] if isinstance(al, list) else [str(al)]
        refus.append(f"alignement : élément inconnu ({', '.join(inconnus)}) — permis : {', '.join(ELEMENTS)}")
    if "prod_outil" in e:
        o, v = verbe("prod_outil")
        if v not in actions.get(o, set()): refus.append(f"prod_outil « {e['prod_outil']} » n'est pas une action (écriture) d'un outil déclaré")
    for cle in ("compte_rendu_outil", "version_servie_outil"):
        if cle in e:
            o, v = verbe(cle)
            if v not in lectures.get(o, set()) or v in actions.get(o, set()):
                refus.append(f"{cle} « {e[cle]} » n'est pas un verbe de lecture d'un outil déclaré")
    if "wiki" in e:
        c = chemin_wiki(e["wiki"])
        if not c: refus.append(f"wiki « {e['wiki']} » refusé : chemin vide, avec « .. » ou des espaces")
        elif zones is None: refus.append("wiki déclaré, mais l'outil wiki de lecture ou ses zones sont introuvables")
        elif not any(dans_zone(c, z) for z in zones): refus.append(f"wiki « {c} » hors des zones de l'outil wiki ({', '.join(map(str, zones))})")
    mods = e.get("modules", {})
    if not isinstance(mods, dict): refus.append("modules : une table [equipes.<projet>.modules] attendue")
    else:
        for nom, m in mods.items():
            if not MODULE.fullmatch(nom) or not isinstance(m, dict):
                refus.append(f"module « {nom} » : nom (lettres, chiffres, _ -) et table {{ chemins, relire }} attendus"); continue
            ch, rel = m.get("chemins", []), m.get("relire", [])
            if not isinstance(ch, list) or not ch or any(not isinstance(x, str) or not x.strip() or ".." in x for x in ch):
                refus.append(f"module « {nom} » : chemins = [\"dossier/\", …] attendus, sans « .. »")
            if not isinstance(rel, list) or any(not isinstance(x, str) or not x.startswith(RELIRE) or not x.split(":", 1)[1].strip() for x in rel):
                refus.append(f"module « {nom} » : chaque relire commence par {', '.join(RELIRE)} (ex. \"wiki:{e.get('wiki') or 'chemin'}/page\")")
    return [f"[equipes.{p}] {x}" for x in refus]
