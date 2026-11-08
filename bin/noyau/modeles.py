"""La table des modèles (`[modeles]` de config.toml) et la règle par type de travail (spec 2026-10-28-modeles, lot 1).

Ce module ne nomme AUCUN moteur : une section `[modeles.<moteur>]` par moteur installé, chacune avec ses niveaux (gros, moyen,
leger) ; `[modeles.types]` donne le niveau de chaque type de travail ; `[modeles.choix]` est réservée aux lots suivants. Le type
voyage dans le texte de la mission, sur une ligne seule « Type : <type> ». Table absente : rien ne change (c'est à l'appelant de
retomber sur l'ancienne liste `[missions] modeles_<moteur>`). Les refus sont des ValueError nommées ; l'appelant les rend."""
import re
from noyau.config import CONFIG
from noyau.lectures import trace_mission     # la ligne 2 se lit à côté de la ligne 1 (reglages_mission), dans lectures.py

NIVEAUX = ("gros", "moyen", "leger")
RESERVEES = ("types", "choix")
LIGNE_TYPE = re.compile(r"(?im)^\s*type\s*:\s*([a-z]+)\s*$")
MOTIF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")      # un nom de modèle ou d'effort : ni saut de ligne, ni espace, ni tiret initial


def nom_sur(v):
    """Vrai si `v` est un nom de modèle ou d'effort sûr (chaîne, motif MOTIF en entier : fullmatch, donc sans saut de ligne final)."""
    return isinstance(v, str) and MOTIF.fullmatch(v) is not None


def controler_lancement(moteur, modele, effort, efforts):
    """Revalide au lancement le modèle (et l'effort) lus dans MISSION.md : ValueError nommée s'ils sont invalides ou si l'effort
    n'est pas permis par le moteur (`efforts`)."""
    if modele is not None and not nom_sur(modele): raise ValueError(f"modèle invalide pour {moteur} : {modele!r} (lettres, chiffres, . _ - ; 64 signes au plus ; pas de tiret initial)")
    if effort is None: return
    if not nom_sur(effort): raise ValueError(f"effort invalide pour {moteur} : {effort!r} (lettres, chiffres, . _ - ; 64 signes au plus ; pas de tiret initial)")
    if effort not in efforts: raise ValueError(f"effort {effort} hors des efforts permis de {moteur} ({', '.join(efforts) or 'aucun'})")


_ABSENTE = object()


def table(t=None):
    """La table `[modeles]` (celle de config.toml, ou `t` pour un essai). {} = clé vraiment absente ; tout ce qui n'est pas une table
    (1, [], false…) est refusé en le nommant : ValueError, jamais pris pour une table absente."""
    v = CONFIG.get("modeles", _ABSENTE) if t is None else t
    if v is _ABSENTE: return {}
    if not isinstance(v, dict): raise ValueError(f"[modeles] doit être une table (trouvé : {type(v).__name__} {v!r})")
    return v


def sections(t=None):
    """{moteur: {niveau: [{modele, effort?}…]}} : tout ce qui n'est pas une table réservée est un moteur."""
    return {k: v for k, v in table(t).items() if k not in RESERVEES and isinstance(v, dict)}


def types(t=None):
    """{type: niveau} de `[modeles.types]`."""
    v = table(t).get("types", {}); return v if isinstance(v, dict) else {}


def verifier_types(t=None):
    """Les défauts de `[modeles.types]` (liste de phrases) : pas une table, niveau qui n'est pas une chaîne connue."""
    v = table(t).get("types", {})
    if not isinstance(v, dict): return [f"[modeles.types] doit être une table « type = niveau » (trouvé : {type(v).__name__})"]
    return [f"[modeles.types] {k} : niveau inconnu {n!r} (niveaux : {', '.join(NIVEAUX)})" for k, n in v.items() if not isinstance(n, str) or n not in NIVEAUX]


def type_du_texte(texte):
    """Le type de travail d'une mission (ligne « Type : <type> »), ou None. Deux lignes différentes : ValueError."""
    vus = {x.lower() for x in LIGNE_TYPE.findall(texte)}
    if len(vus) > 1: raise ValueError(f"deux lignes « Type : » différentes ({', '.join(sorted(vus))}) : une seule par mission")
    return next(iter(vus), None)


def verifier(moteur, efforts, t=None):
    """Les défauts de la section d'un moteur (liste de phrases, vide = bonne) : section absente, niveau inconnu ou manquant,
    entrée sans modèle, effort hors de `efforts` (les efforts permis par le moteur)."""
    s = sections(t).get(moteur)
    if s is None: return [f"moteur {moteur} sans section [modeles.{moteur}] : il n'entre pas dans le choix (moteurs de la table : {', '.join(sections(t)) or 'aucun'})"]
    pb = [f"niveau inconnu pour {moteur} : {n} (niveaux : {', '.join(NIVEAUX)})" for n in s if n not in NIVEAUX]
    for n in NIVEAUX:
        es = s.get(n)
        if not es: pb.append(f"[modeles.{moteur}] : niveau {n} absent"); continue
        if not isinstance(es, list): pb.append(f"[modeles.{moteur}] {n} : une liste d'entrées {{modele = …}} est attendue (trouvé : {type(es).__name__})"); continue
        for e in es:
            if not isinstance(e, dict): pb.append(f"[modeles.{moteur}] {n} : entrée {e!r} : une table {{modele = …}} est attendue"); continue
            if not nom_sur(e.get("modele")): pb.append(f"[modeles.{moteur}] {n} : modèle invalide {e.get('modele')!r} (lettres, chiffres, . _ - ; 64 signes au plus ; pas de tiret initial)"); continue
            f = e.get("effort")
            if f is None: continue
            if not nom_sur(f): pb.append(f"[modeles.{moteur}] {n} / {e['modele']} : effort invalide {f!r}")
            elif f not in efforts: pb.append(f"effort {f} hors des efforts permis de {moteur} ({', '.join(efforts) or 'aucun'}) : {n} / {e['modele']}")
    return pb


def decider(moteur, modele, texte, par, niveau_agent, efforts, t=None):
    """(modèle, niveau, raison, effort) d'une mission pour `moteur`, table PRÉSENTE. Un modèle explicite doit figurer dans la table
    du moteur (le niveau est celui de la table) ; sinon le type (ou, à défaut, `niveau_agent`) donne le niveau et le premier modèle
    du niveau convient. Jamais de repli sur le gros modèle. `efforts` : les efforts permis du moteur."""
    pb = verifier(moteur, efforts, t) + verifier_types(t)
    if pb: raise ValueError(pb[0])
    s = sections(t)[moteur]; tp = type_du_texte(texte); rt = types(t)
    if tp and tp not in rt: raise ValueError(f"type de travail inconnu : {tp} (types : {', '.join(sorted(rt)) or 'aucun'})")
    if modele:
        for n in NIVEAUX:
            for e in s[n]:
                if e["modele"] == modele: return modele, n, f"choix explicite de {par}" + (f" ; type {tp}" if tp else ""), e.get("effort")
        permis = [e["modele"] for n in NIVEAUX for e in s[n]]
        raise ValueError(f"modèle {modele} inconnu pour {moteur} : table [modeles.{moteur}] (permis : {', '.join(permis)})")
    if tp: niveau, raison = rt[tp], f"type {tp} (règle)"
    elif niveau_agent: niveau, raison = niveau_agent, "niveau de l'agent (agent.conf)"
    else: raise ValueError("type de travail manquant (ligne « Type : spec », « Type : code »… dans la mission, ou « niveau = » dans agent.conf)")
    if not isinstance(niveau, str) or niveau not in NIVEAUX: raise ValueError(f"niveau inconnu : {niveau} (niveaux : {', '.join(NIVEAUX)})")
    e = s[niveau][0]
    return e["modele"], niveau, raison, e.get("effort")


def ligne_trace(niveau, raison, effort):
    """La ligne 2 de MISSION.md (avec son saut de ligne en tête, prête à suivre la ligne 1)."""
    return f"\nniveau : {niveau} · raison : {raison}" + (f" · effort : {effort}" if effort else "")
