"""Les LECTURES des équipes (modulaire, lot 4c) : ce qu'une famille de commandes ou une vue peut lire d'une équipe de développement, sans rien écrire.

Code déplacé de bin/berger (section « équipes ») : aucun comportement changé. Ouvrir et fermer un développeur, changer un site permis, inscrire un go,
ouvrir et fermer un projet, jouer le crochet sont des ACTIONS : elles ne sont pas ici, mais derrière les services de noyau/actions.py (leurs contrôles
restent dans le geste, au cœur). Le cœur importe d'ici, par leur nom, ce que ses gestes et le calcul du mur relisent (registre des projets, sites permis,
section d'équipe) : mêmes objets, aucun recopié. Dépendances nommées, aucun `import *`."""
import json, os, re, sys
from pathlib import Path
from noyau.config import BERGER
from noyau.lectures import EQUIPES
from noyau.agents import agents, checklist, conf, dossier, lire


# Sites permis par projet (12/10/2026, docs/plans/archive/2026-10-12-domaines-projet-spec.md) : equipes/<projet>/domaines de
# l'installation (hors de toute écriture d'agent), un nom EXACT par ligne — pas de joker, d'IP ni de port. Écrite par
# `berger equipe domaine` (verbe du courtier validé par le superviseur), jamais à la main.
DOMAINE = re.compile(r"(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")
DOMAINES_MAX = 30


def domaines_projet(p, signaler=True):
    """Sites permis du projet `p` : la liste validée ; une ligne retouchée à la main qui n'est pas un nom exact est IGNORÉE
    (jamais un joker ouvert par erreur) et signalée."""
    l = []
    for x in lire(BERGER / "equipes" / p / "domaines").splitlines():
        x = x.split("#")[0].strip()
        if not x or x in l: continue
        if DOMAINE.fullmatch(x): l.append(x)
        elif signaler: print(f"⚠ equipes/{p}/domaines : « {x[:60]} » n'est pas un nom de domaine exact — ignoré")
    return sorted(l)[:DOMAINES_MAX]


def registre_projets(eq):
    """Projets ouverts d'une équipe : {projet: {membres, ouvert, par}}. Le registre vit HORS de la bibliothèque
    (equipes/<équipe>/projets.json de l'installation) : un membre, qui écrit dans le dossier du projet, ne peut pas s'y ajouter
    quelqu'un ni lever les droits. Écrit par berger seul (hors bac à sable)."""
    try: return json.loads((BERGER / "equipes" / eq / "projets.json").read_text())
    except (OSError, ValueError): return {}


def _equipe(projet):
    e = EQUIPES.get(projet) or sys.exit(f"projet d'équipe inconnu : {projet} (section [equipes.{projet}] de config.toml)")
    depot = Path(os.path.expanduser(e["depot"]))
    # Jamais l'installation en service : une fusion y serait un DÉPLOIEMENT sans relecture (09/10/2026). Pour corriger
    # Berger, l'équipe travaille dans un clone séparé, sur une forge locale (README › Master).
    if depot.resolve() == BERGER.resolve(): sys.exit(f"[equipes.{projet}] : le dépôt ne peut pas être l'installation ({BERGER}) — un clone séparé (ex. ~/projets/berger)")
    return e, depot, e.get("principale", "main")


def equipe_liste(projet):
    _equipe(projet); out = []
    dem = BERGER / "equipes" / projet / "demandes"
    for a in agents():
        c = conf(a)
        if c.get("projet") != projet or not c.get("sujet"): continue
        ck = checklist(a); f = dem / f"{c['sujet']}.json"
        d = json.loads(f.read_text()) if f.is_file() else {}
        out.append({"agent": a, "sujet": c["sujet"], "branche": c["branche"], "port": c.get("port"),
                    "mission": (dossier(a) / "MISSION.md").is_file(), "checklist": ck and f"{ck['faites']}/{ck['total']}",
                    "bloque": (ck or {}).get("bloque"), "demande_de_fusion": d.get("etat"), "portes": resume_portes(d.get("portes")),
                    "renvois": int(d.get("renvois", 0))})
    for a in agents():                                                    # [equipes.<projet>] fait foi (spec 2026-10-13)
        if f"equipe:{projet}" in [x.strip() for x in conf(a).get("outils", "").split(",")] and a != EQUIPES[projet].get("coordinateur"):
            out.append({"avertissement": f"{a} déclare equipe:{projet} sans être le coordinateur déclaré : ignoré, à retirer de son agent.conf"})
    return out


def resume_portes(res):
    """« verify : vert ; tests : vert ; … » d'une demande de fusion (None sans demande)."""
    return " ; ".join(f"{p} : {r.get('etat')}" for p, r in res.items()) if isinstance(res, dict) and res else None


def projet_liste(eq=None):
    return {e: registre_projets(e) for e in ([eq] if eq else EQUIPES)}


__all__ = ('DOMAINE', 'DOMAINES_MAX', 'domaines_projet', 'registre_projets', 'equipe_liste', 'projet_liste')
