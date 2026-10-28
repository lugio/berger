# Vue « Sources » de Berger : berger panneau sources. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → sources.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Sources"
ICONE = '🔎'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 3


def donnees(a=None):
    """Le dernier résultat de chaque panneau déclaré (relu dans courtier/panneaux/, jamais relancé ici), son état
    (ok, échec, figé, attente) et ses lignes avec leur gravité. `a` : « nom,nom » (ou une liste) = seulement ces sources (un nom non
    déclaré est rendu dans `inconnues`, pas ignoré). Chaque ligne : `texte` nu, et `terminal` (couleurs de l'outil gardées,
    tout autre code retiré) pour le rendu texte."""
    noms = list(a) if isinstance(a, list) else (a.split(",") if a else None)
    choisies = PANNEAUX_SOURCES if noms is None else {n: PANNEAUX_SOURCES[n] for n in noms if n in PANNEAUX_SOURCES}
    sources = []
    for nom, p in choisies.items():
        etat_, r = etat_source(nom, p)
        lignes = [propre(l) for l in r.get("lignes", [])] if etat_ != "attente" else []; maxi = int(p.get("max_lignes", 12))
        sources.append({"nom": nom, "titre": str(p.get("titre", nom)), "outil": str(p.get("outil")), "verbe": str(p.get("verbe")),
                        "etat": etat_, "quand": str(r.get("quand", "")), "duree": r.get("duree", "?"),
                        "erreur": (r.get("erreur") or "code " + str(r.get("code"))) if etat_ == "echec" else None,
                        "cadence": p.get("cadence", 300),
                        "lignes": [{"texte": ANSI.sub("", l), "terminal": l, "gravite": gravite(l, p)} for l in lignes[:maxi]],
                        "en_plus": max(0, len(lignes) - maxi)})
    return {"filtre": noms, "declarees": len(PANNEAUX_SOURCES), "inconnues": [n for n in (noms or []) if n not in PANNEAUX_SOURCES],
            "sources": sources}


def rendu_texte(d, w, h):
    """SOURCES : lignes rouges et jaunes en couleur. Une collecte en échec le DIT (le panneau n'affiche pas zéro) ; un
    résultat trop vieux est marqué figé."""
    entete_ = (f" 🔎 SOURCES  ·  {d['declarees']} outil(s) relu(s) par le courtier" if d["filtre"] is None
               else " 🔎 " + " · ".join(s["titre"] for s in d["sources"]))
    out = [INV + GRAS + pad(couper(entete_, w - 8), w - 7) + f"{datetime.datetime.now():%H:%M}  " + R]
    if d["inconnues"]: out += plier(f"○ source(s) non déclarée(s) dans config.toml : {', '.join(d['inconnues'])} ([panneaux.<nom>])", w - 2, "  " + ROUGE, "    ", ROUGE)
    if not d["sources"]: return out + ["", PALE + "  aucun panneau déclaré : [panneaux.<nom>] dans config.toml (outil, verbe, cadence)" + R]
    for s in d["sources"]:
        quand = s["quand"][11:16]
        out += [""] + titre_section(f"{s['titre']}  ·  {s['outil']} {s['verbe']}", CYAN, w)
        if s["etat"] == "attente": out.append(PALE + "  ○ pas encore collecté (le courtier tourne-t-il ?)" + R); continue
        if s["etat"] == "echec":
            out += plier(f"○ collecte en échec à {quand} — {s['erreur']} — le panneau n'affiche PAS zéro", w - 2, "  " + ROUGE, "    ", ROUGE)
        elif s["etat"] == "fige": out.append(JAUNE + f"  ○ figé : dernière collecte à {quand} (cadence {s['cadence']} s)" + R)
        else: out.append(PALE + f"  collecté à {quand} en {s['duree']} s" + R)
        for l in s["lignes"]:
            out.append(couper("  " + ({"rouge": ROUGE, "jaune": JAUNE}.get(l["gravite"], "")) + l["terminal"] + R, w))
        if s["en_plus"]: out.append(PALE + f"  … {s['en_plus']} ligne(s) de plus" + R)
    return out


def vue_sources(w, h, noms=None):
    return rendu_texte(donnees(noms), w, h)


def rendre(w, h, a=None):
    return vue_sources(w, h, a.split(",") if a else None)
