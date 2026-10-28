# Vue « À lire » de Berger : berger panneau alire. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → alire.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "À lire"
ICONE = '📖'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 6


def donnees(a=None):
    docs = documents_a_lire(); vus = lus()
    return {"documents": [{"id": id_document(d), "auteur": agent_court(d["auteur"]) if d["auteur"] else None, "titre": d["titre"],
                           "date": quand_iso(d["date"]), "lu": d["cle"] in vus, "regle": d["regle"]} for d in docs],
            "non_lus": sum(d["cle"] not in vus for d in docs)}


def rendu_texte(d, w, h):
    docs = d["documents"]; non_lus = d["non_lus"]
    out = [INV + GRAS + pad(f" À LIRE  ·  {non_lus} non lu{'s' if non_lus > 1 else ''} sur {len(docs)}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    for n, x in enumerate(docs, 1):
        qui = f"{x['auteur']['icone']} {x['auteur']['nom']}" if x["auteur"] else "📌 commun"
        neuf = not x["lu"]
        out.append(couper(f" {(JAUNE + '●' + R) if neuf else (PALE + '✓' + R)} {GRAS if neuf else PALE}{n:>2}{R}  {pad(qui, 16)} "
                          f"{PALE}{datetime.datetime.fromisoformat(x['date']):%d/%m %H:%M}{R}  {GRAS if neuf else ''}{x['titre']}{R}"
                          + (f"{PALE}  — réglé : {x['regle']}{R}" if x["regle"] else ""), w))
    if not docs: out.append(PALE + "  rien à lire — les agents déposent leurs rapports dans agents/<agent>/a-lire/" + R)
    return out


def vue_alire(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_alire(w, h)
