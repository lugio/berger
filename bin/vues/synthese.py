# Vue « Synthèse » de Berger : berger panneau synthese. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → synthese.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Synthèse"
ICONE = '🚦'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 2


def donnees(a=None):
    """Le rouge et le jaune (alertes_synthese), avec la première apparition de chacun (depuis) ; NOUVEAU = moins de 24 h."""
    al = alertes_synthese(); quand = depuis(al); maintenant = datetime.datetime.now()
    return {"alertes": [{"gravite": g, "domaine": dom, "texte": t, "depuis": q,
                         "nouveau": maintenant - datetime.datetime.fromisoformat(q) < datetime.timedelta(hours=24)}
                        for (g, dom, t), q in zip(al, quand)],
            "surveille": ["courtier", "audit des secrets", "sauvegarde", "auto-test", "validations", "agents", f"{len(PANNEAUX_SOURCES)} source(s)"]}


def rendu_texte(d, w, h):
    """SYNTHÈSE (même règle que celle du 113) : seulement le ROUGE et le JAUNE, le rouge d'abord, avec depuis quand ;
    NOUVEAU = apparu il y a moins de 24 h. Rien à signaler : une ligne verte qui dit ce qui est surveillé."""
    out = [INV + GRAS + pad(" 🚦 SYNTHÈSE  ·  rouge et jaune seulement", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R]
    al = d["alertes"]
    if not al:
        return out + ["", VERT + GRAS + "  ✓ rien en rouge ni en jaune" + R, PALE + f"  surveillé : {', '.join(d['surveille'])}" + R]
    for g, lib, coul in (("rouge", "ROUGE", ROUGE), ("jaune", "JAUNE", JAUNE)):
        mes = [x for x in al if x["gravite"] == g]
        if not mes: continue
        out += [""] + titre_section(f"{lib} ({len(mes)})", coul, w)
        vus = {}                                                             # au plus 3 lignes par domaine : un fait, pas une liste
        for x in mes:
            dom = x["domaine"]; vus[dom] = vus.get(dom, 0) + 1
            if vus[dom] > 3: continue
            q = datetime.datetime.fromisoformat(x["depuis"])
            fin = f"  {GRAS + 'NOUVEAU' + R + PALE if x['nouveau'] else ''} depuis le {q:%d/%m %H:%M}"
            out += plier(f"{GRAS}{dom}{R}{coul} : {x['texte']}{R}{PALE}{fin}{R}", w - 2, f"  {coul}●{R} {coul}", "    ")
        for dom, n in vus.items():
            if n > 3: out.append(couper(f"  {coul}●{R} {GRAS}{dom}{R}{PALE} : … et {n - 3} autre(s) du même genre — onglet Sources{R}", w))
    out += ["", couper(PALE + "  détail : onglet Sources (outils) · Accueil (validations) · Courtier (audit, sauvegarde)" + R, w)]
    return out


def vue_synthese(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_synthese(w, h)
