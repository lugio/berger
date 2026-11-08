# Vue « Extensions » de Berger (spec docs/plans/2026-11-07-extensions-spec.md § 6, go n° 181, lot 2) : une carte par extension installée — genre,
# nom, version, empreinte courte, agents, droits accordés (réseau en évidence), date d'installation, dernier usage, état (active, ou écartée avec
# la raison). LECTURE SEULE : rien ne s'installe ni ne se retire d'ici (`berger extension …`, au terminal). Les données viennent filtrées du noyau
# (extensions_donnees : liste blanche des champs, forme de clé et marque privée masquées, aucun chemin privé, coffre jamais lu).
# Page web seulement (HERDR = False) ; `berger vue extensions` en donne le texte.
TITRE = "Extensions"
ONGLET = "berger"     # après les onglets de l'espace Berger (web seulement)
ORDRE = 10
HERDR = False         # aucun onglet dans l'espace Herdr


def donnees(a=None):
    return extensions_donnees()


def rendu_texte(d, w, h):
    out = [INV + GRAS + pad(" EXTENSIONS  ·  lecture seule", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    out += plier(f"Installer, retirer, revenir : berger extension … (au terminal) ; état dans {d['fichier']}.", w, "  ", "  ", PALE)
    if d["signalements"]:
        out += [""] + titre_section(f"À SIGNALER ({len(d['signalements'])})", JAUNE, w)
        for x in d["signalements"]:
            out += plier(f"{x['quoi']} → {x['consequence']}", w, (ROUGE if x["ton"] == "rouge" else JAUNE) + "  ⚠ " + R, "    ")
    out += [""] + titre_section(f"INSTALLÉES ({len(d['extensions'])})", CYAN, w)
    if not d["extensions"]: out.append(PALE + "  aucune extension installée" + R)
    for x in d["extensions"]:
        ton = VERT if x["etat"] == "active" else ROUGE
        out.append(couper(GRAS + f"  {x['nom']}" + R + f"  {x['genre']} {x['version']} · {x['empreinte']}  " + ton + x["etat"] + R
                          + (ROUGE + GRAS + "  · RÉSEAU" + R if x["reseau"] else ""), w))
        if x["description"]: out += plier(x["description"], w, "    ", "    ", PALE)
        out.append(couper(f"    agents : {', '.join(x['agents']) or 'personne'} ; installée le {x['installee']} ; dernier usage : {x['dernier_usage']}", w))
        if x["droits"]: out.append(couper("    droits : " + " ; ".join(f"{r['cle']} = {r['valeur']}" for r in x["droits"]), w))
    return out


def vue_extensions(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_extensions(w, h)
