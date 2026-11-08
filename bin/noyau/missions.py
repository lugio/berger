"""Les LECTURES des missions (modulaire, lot 4a) : ce qu'une famille de commandes ou une vue peut lire d'une mission, sans rien écrire.

Code déplacé de bin/berger (section « missions ») : aucun comportement changé. Confier et terminer une mission sont des ACTIONS : elles ne sont pas ici,
mais derrière les services de noyau/actions.py (leurs contrôles restent dans le service). Dépendances nommées, aucun `import *`."""
import json, sys
import noyau.modeles
from noyau.config import BERGER
from noyau.agents import aujourdhui, checklist, conf, dossier, lire
from noyau.herdr import herdr, herdr_ids, statut_herdr
from noyau.lectures import hote_mission, reglages_mission


def agent_vivant(a):
    """Au moins un panneau de l'agent existe encore dans Herdr (dans son espace ou dans un onglet Missions)."""
    return any(herdr("pane", "get", p).get("pane") for p in herdr_ids(a).get("agents", {}).values())


def suivi(a):
    """État d'une mission, en JSON : statut Herdr, mission, checklist, journal récent, validations en attente."""
    if not (dossier(a) / "agent.conf").is_file(): sys.exit(f"agent inconnu : {a}")
    ids = herdr_ids(a).get("agents", {}); ouvert_ = agent_vivant(a)
    ck = checklist(a); jf = dossier(a) / "memory" / f"{aujourdhui()}.md"
    attente = [json.loads(x.read_text()) for x in sorted((BERGER / "courtier/validations").glob("*.json"))
               if not x.name.endswith(".fait.json")] if (BERGER / "courtier/validations").is_dir() else []
    mm, modele = reglages_mission(a)
    return {"agent": a, "nom": conf(a)["nom"], "agent_ouvert": ouvert_, "ou": f"onglet Missions de {hote_mission(a)}" if hote_mission(a) else "son espace",
            "moteur": mm, "modele": modele, **dict(zip(("niveau", "raison", "effort"), noyau.modeles.trace_mission(a))),
            "statut": {m: statut_herdr(p) for m, p in ids.items()} if ouvert_ else {},
            "mission": lire(dossier(a) / "MISSION.md").strip() or None,
            "checklist": ck and {k: ck[k] for k in ("titre", "faites", "total", "en_cours", "bloque", "fini")},
            "journal": [l[2:] for l in lire(jf).splitlines() if l.startswith("- ")][-8:],
            "validations_en_attente": [f"n° {d['n']} : {d['apercu']}" for d in attente if d.get("agent") == a]}


def rapport_mission(a, max_docs=3, max_car=20000):
    """Ce que l'agent en mission a rendu : ses documents de a-lire/ écrits depuis le début de la mission en cours (date de
    MISSION.md), les plus récents d'abord. Celui qui a confié la mission ne peut pas lire le dossier de l'agent (agents
    séparés) : c'est par ici, via le courtier, qu'il relit le rapport avant de terminer."""
    m = dossier(a) / "MISSION.md"
    if not m.is_file(): sys.exit(f"{conf(a)['nom']} n'a pas de mission en cours")
    debut = m.stat().st_mtime - 5
    docs = [f for f in sorted((dossier(a) / "a-lire").glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
            if f.is_file() and not f.is_symlink() and f.stat().st_mtime >= debut][:max_docs]
    return {"agent": a, "nom": conf(a)["nom"], "documents": [{"fichier": f.name, "texte": lire(f)[:max_car],
                                                              "tronque": len(lire(f)) > max_car} for f in docs]}


__all__ = ("agent_vivant", "suivi", "rapport_mission")
