# Vue « Documents » de Berger (spec interface §6.1 bis ; demande du propriétaire du 14/10 : une mini GED, en consultation
# seule) : berger vue documents. Les fichiers de la bibliothèque (commun, projets d'équipe, dossiers de travail), des À lire
# et des branches en cours — documents() du cœur, le SEUL lister (Livrables en est un filtre). Un document s'ouvre par la vue
# d'objet `livrable` (son id, jamais un chemin) ; la page range par origine et dossier et filtre par nom ce qu'elle a reçu.
TITRE = "Documents"
ICONE = '🗂'
ONGLET = "berger"     # juste après Livrables
ORDRE = -1

ORIGINES = {"commun": "commun", "projet": "projet", "travail": "travail", "a_lire": "À lire", "branche": "branche"}


def donnees(a=None):
    return {"documents": [{"id": x["id"], "titre": x["titre"], "auteur": agent_court(x["auteur"]) if x["auteur"] else None,
                           "origine": x["origine"], "projet": x["projet"], "branche": x["branche"], "chemin": x["chemin"],
                           "genre": x["genre"], "taille": x["taille"], "date": quand_iso(x["date"]), "lu": x["lu"],
                           "lien": {"vue": "livrable", "a": x["id"]}} for x in documents()]}


def rendu_texte(d, w, h):
    l = d["documents"]
    out = [INV + GRAS + pad(f" DOCUMENTS  ·  {len(l)}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    for o, libelle in ORIGINES.items():
        mes = [x for x in l if x["origine"] == o]
        if not mes: continue
        out.append(GRAS + f" {libelle} ({len(mes)})" + R)
        for x in mes:
            ou = (f"{x['projet']} · " if x["projet"] else "") + (f"{x['branche']} · " if x["branche"] else "") + x["chemin"]
            out.append(couper(f"  {PALE}{datetime.datetime.fromisoformat(x['date']):%d/%m %H:%M}{R}  {pad(x['genre'], 5)} {x['titre']}  {PALE}{ou}{R}", w))
    if not l: out.append(PALE + "  aucun document — la bibliothèque (commun, projets, travail) et les À lire sont vides" + R)
    return out


def vue_documents(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_documents(w, h)
