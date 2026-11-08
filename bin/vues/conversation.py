# Vue « Conversation » de Berger (interface web v2, lot 3 ; spec docs/plans/2026-11-05-interface-web-v2-lot3-spec.md, go n° 166) : le fil
# de messagerie d'un agent, lu en LECTURE seule dans la vraie conversation de son moteur (fil_conversation du noyau). Ouverte seulement
# pour les agents déclarés ([conversation] agents de config.toml) ; jamais la sortie d'un outil ; chaque bloc passe par MOTIFS_CLES.
TITRE = "Conversation"
ONGLET = "agent"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 23


def donnees(a=None):
    binaire, raison = transcription_locale()
    return {"agent": agent_court(a), "statuts": statuts_donnees(a), **fil_conversation(a),
            "micro": {"actif": binaire is not None, "raison": raison}}


def rendu_texte(d, w, h):
    out = [entete(d["agent"], "conversation", w, statuts_texte(d["statuts"])), ""]
    if not d["ouverte"]: return out + plier(d["raison"], w, "  ", "  ", PALE)
    corps = []
    for t in d["tours"]:
        heure = (t["quand"] or "")[11:16] or "     "
        if t["genre"] == "actions": corps.append(f"  {PALE}{heure}  {len(t['actions'])} action{'s' if len(t['actions']) > 1 else ''}{R}")
        elif t["genre"] == "validation":
            v = t["validation"]; corps += plier(f"n° {v['n']} · {v['apercu']}", w, f"  {JAUNE}{heure}  ✎ {R}", "         ")
        else: corps += plier(plat(t["texte"]), w, f"  {CYAN if t['genre'] == 'proprio' else VERT}{heure}{R}  {'toi : ' if t['genre'] == 'proprio' else ''}", "         ")
    place = max(3, h - len(out) - 2)
    if len(corps) > place: corps = [PALE + f"  … {len(corps) - place + 1} lignes plus haut" + R] + corps[-(place - 1):]
    if not d["vivant"]: corps.append(PALE + "  " + (d["raison"] or "") + R)
    return out + (corps or [PALE + "  aucun message" + R])


def vue_conversation(a, w, h):
    return rendu_texte(donnees(a), w, h)


def rendre(w, h, a=None):
    return vue_conversation(a, w, h)
