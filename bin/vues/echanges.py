# Vue « Échanges » de Berger : berger panneau echanges. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → echanges.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Échanges"
ICONE = '💬'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 8


def donnees(a=None):
    """Les 800 dernières lignes du journal des échanges (avec un agent : seulement ce qu'il a reçu ou envoyé)."""
    ev = []
    for l in lire(ECHANGES).splitlines()[-800:]:
        try: e = json.loads(l)
        except ValueError: continue
        if a is None or a in (e.get("de"), e.get("a")):
            ev.append({"quand": str(e.get("quand", "")), "de": agent_court(e.get("de")), "a": agent_court(e.get("a")),
                       "genre": str(e.get("genre", "")), "texte": str(e.get("texte", ""))})
    return {"agent": agent_court(a) if a else None, "proprietaire": PROPRIETAIRE, "echanges": ev}


def rendu_texte(d, w, h):
    """Le fil des échanges entre le propriétaire et les agents, le plus récent en bas (ce qui tient à l'écran)."""
    titre = f"ÉCHANGES de {d['agent']['nom']}" if d["agent"] else "ÉCHANGES"
    out = [INV + GRAS + pad(f" {titre}  ·  {d['proprietaire']} et les agents", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    couleur = {"mission": BLEU, "fin de mission": BLEU, "question": CYAN, "réponse": CYAN, "validation demandée": JAUNE,
               "validée": VERT, "refusée": ROUGE, "validée, en échec": ROUGE, "demande de fusion": JAUNE}
    blocs = []
    for e in d["echanges"]:
        q = e["quand"]
        tete = (f"{PALE}{q[8:10]}/{q[5:7]} {q[11:16]}{R}  {GRAS}{e['de']['nom']}{R} {PALE}→{R} "
                f"{GRAS}{e['a']['nom']}{R}  {couleur.get(e['genre'], PALE)}{e['genre']}{R}")
        blocs.append([tete] + plier(plat(e["texte"]), w, "    ")[:5])
    place = h - len(out) - 2; montres = []
    for b in reversed(blocs):
        if len(b) + 1 > place: break
        montres.insert(0, b); place -= len(b) + 1
    if len(montres) < len(blocs): out.append(PALE + f"  … {len(blocs) - len(montres)} échange(s) plus haut" + R)
    for b in montres: out += b + [""]
    if not blocs: out.append(PALE + "  aucun échange pour l'instant : messages, missions, délégations, validations et demandes "
                             "de fusion apparaîtront ici" + R)
    return out


def vue_echanges(a, w, h):
    return rendu_texte(donnees(a), w, h)


def rendre(w, h, a=None):
    return vue_echanges(a, w, h)
