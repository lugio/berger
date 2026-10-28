# Vue « Livrables » de Berger (spec interface §6.1, lot 1b ; demande du propriétaire du 14/10 : « la page dédiée aux maquettes ») :
# berger vue livrables. Specs, maquettes et rapports déposés là où la règle « livrables visibles » les met — bibliothèque
# (agents/<agent>/travail/), À lire, docs/plans et docs/apercu des branches en cours — livrables() du cœur, un
# filtre de documents(), le seul lister (§6.1 bis). Un livrable s'ouvre par la vue d'objet `livrable` (son id, jamais un chemin).
TITRE = "Livrables"
ICONE = '📐'
ONGLET = "berger"     # en tête de la navigation (demande du propriétaire), juste après l'Accueil dans Herdr
ORDRE = -2

ORIGINES = {"commun": "commun", "projet": "projet", "travail": "travail", "a_lire": "À lire", "branche": "branche"}


def donnees(a=None):
    return {"livrables": [{"id": x["id"], "titre": x["titre"], "auteur": agent_court(x["auteur"]) if x["auteur"] else None,
                           "origine": x["origine"], "projet": x["projet"], "branche": x["branche"], "chemin": x["chemin"],
                           "genre": x["genre"], "taille": x["taille"], "date": quand_iso(x["date"]), "lu": x["lu"],
                           "lien": {"vue": "livrable", "a": x["id"]}} for x in livrables()]}


def rendu_texte(d, w, h):
    l = d["livrables"]
    out = [INV + GRAS + pad(f" LIVRABLES  ·  {len(l)}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    for x in l:
        qui = f"{x['auteur']['icone']} {x['auteur']['nom']}".strip() if x["auteur"] else "📌 commun"
        ou = ORIGINES[x["origine"]] + (f" {x['projet']} · {x['branche']}" if x["branche"] else "")
        out.append(couper(f"  {PALE}{datetime.datetime.fromisoformat(x['date']):%d/%m %H:%M}{R}  {pad(x['genre'], 5)} {pad(qui, 16)} "
                          f"{GRAS}{x['titre']}{R}  {PALE}{ou} · {x['chemin']}{R}", w))
    if not l: out.append(PALE + "  aucun livrable — les agents déposent specs, maquettes et rapports dans la bibliothèque (travail/<sujet>/) ou À lire" + R)
    return out


def vue_livrables(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_livrables(w, h)
