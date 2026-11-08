# Vue « Réglages » de Berger (spec docs/plans/2026-11-05-interface-reglages-spec.md, go n° 169) : config.toml par sections, en LECTURE
# SEULE, une phrase simple par réglage connu ; les valeurs sensibles arrivent DÉJÀ masquées (« [masqué] ») par le lecteur du noyau
# (noyau/reglages.py, via reglages_donnees) — ni cette vue ni la page ne voient jamais la valeur. Le coffre n'est jamais lu.
# Page web seulement (HERDR = False) : le serveur de l'interface sert ces mêmes données EN DIRECT (il dit ainsi « config.toml invalide »
# même quand `berger` ne démarre plus) ; `berger vue reglages` en donne le texte.
TITRE = "Réglages"
ONGLET = "berger"     # après les onglets de l'espace Berger (web seulement)
ORDRE = 9
HERDR = False         # aucun onglet dans l'espace Herdr : les réglages se lisent dans la page web, ou dans config.toml


def donnees(a=None):
    return reglages_donnees()


def rendu_texte(d, w, h):
    out = [INV + GRAS + pad(" RÉGLAGES  ·  lecture seule", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    out += plier(f"Ces réglages se changent dans {d['fichier']}.", w, "  ", "  ", PALE)
    if d["signalements"]:
        out += [""] + titre_section(f"À SIGNALER ({len(d['signalements'])})", JAUNE, w)
        for x in d["signalements"]:
            out += plier(f"{x['quoi']} → {x['consequence']}", w, (ROUGE if x["ton"] == "rouge" else JAUNE) + "  ⚠ " + R, "    ")
    for s in d["sections"]:
        out += [""] + titre_section(s["titre"].upper(), CYAN, w)
        if s["phrase"]: out += plier(s["phrase"], w, "  ", "  ", PALE)
        for c in s["cartes"]:
            if c["titre"]: out.append(GRAS + f"  {c['titre']}" + R)
            for r in c["reglages"]:
                out.append(couper(f"    {r['cle']} = {r['valeur']}" + ("" if r["phrase"] == "réglage non décrit" else f"  {PALE}· {r['phrase']}{R}"), w))
    return out


def vue_reglages(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_reglages(w, h)
