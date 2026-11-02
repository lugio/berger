# Vue « Accueil » de Berger : berger panneau accueil. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → accueil.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Accueil"
ICONE = '🏠'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 0


def donnees(a=None):
    """Ce qui attend le propriétaire (écritures, blocages, documents non lus), puis chaque agent et chaque équipe."""
    att = [validation_donnees(d) for d in en_attente()]; vus = lus()
    devs = sorted(x for x in agents() if conf(x).get("sujet"))
    equipes = []
    for p_ in EQUIPES:
        dem = {}
        def date_fusion(f):
            d = json_ou_rien(f) or {}
            return str(d.get('fusionnee') or datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat())
        for f in sorted((BERGER / "equipes" / p_ / "demandes").glob("*.json"), key=date_fusion):
            d = json_ou_rien(f)
            if d: dem[d.get("sujet", f.stem)] = d.get("etat")
        membres = []
        for x in [x for x in devs if conf(x).get("projet") == p_]:
            ck = checklist(x)
            membres.append({"agent": agent_court(x), "sujet": conf(x)["sujet"], "statuts": statuts_donnees(x),
                            "faites": ck["faites"] if ck else None, "total": ck["total"] if ck else None, "demande": dem.get(conf(x)["sujet"])})
        e_ = EQUIPES[p_]                                                   # qui répond de l'équipe ([equipes.<p>]) : affiché par l'interface
        equipes.append({"projet": p_, "chef": agent_court(e_["chef_projet"]) if e_.get("chef_projet") else None,
                        "coordinateur": agent_court(e_["coordinateur"]) if e_.get("coordinateur") else None,
                        "membres": membres, "fusionnes": [s_ for s_, e_ in dem.items() if e_ == "fusionnée"]})
    al = alertes_synthese(); quand = depuis(al); maintenant = datetime.datetime.now()      # le rouge et le jaune de la Synthèse, en tête de l'Accueil
    return {"alertes": [{"gravite": g, "domaine": dom, "texte": t, "depuis": q,
                         "nouveau": maintenant - datetime.datetime.fromisoformat(q) < datetime.timedelta(hours=24)} for (g, dom, t), q in zip(al, quand)],
            "agents_total": len(agents()),
            "a_toi": [d for d in att if not d["valideur"]], "delegues": [d for d in att if d["valideur"]],
            "bloques": [{"agent": agent_court(x), "bloque": checklist(x)["bloque"]} for x in agents() if (checklist(x) or {}).get("bloque")],
            "a_lire": [{"id": id_document(d), "titre": d["titre"]} for d in documents_a_lire() if d["cle"] not in vus],
            "agents": [{"agent": agent_court(x), "statuts": statuts_donnees(x), "checklist": checklist_donnees(checklist(x)),
                        "derniere_action": derniere_action(x)} for x in agents() if x not in devs],
            "equipes": equipes, "attentes": decisions(), "tableau": {"colonnes": [{"cle": c, "libelle": l, "ton": t} for c, l, t in COLONNES_TONS], "cartes": cartes_donnees()}}


def ligne_attente(x, w):
    """Un élément qui attend le propriétaire, en phrases de patron (sans chemin ni jargon) : une ligne, plus ses commandes à copier."""
    if x["genre"] == "validation":
        out = [couper(f"  {ROUGE}●{R} {GRAS}Écriture n° {x['n']}{R} · {phrase_patron(x['titre'].split(' · ', 1)[-1], 24)} : {phrase_patron(x['detail'].split('  →', 1)[0], 90)}", w)]
        return out + [f"      {GRAS}berger valider {x['n']}{R}", f"      {GRAS}berger refuser {x['n']}{R}"]
    return [couper(f"  {ROUGE}●{R} {GRAS}{x['titre']}{R} : {phrase_patron(x['detail'], 100)}", w)]


def tableau_compact(t, w, maxi=4):
    """Le Tableau (mêmes 5 colonnes, mêmes tons) en version courte : une ligne par carte, `maxi` cartes par colonne. Les colonnes vides se contentent de leur
    titre ; l'espace restant va aux colonnes qui ont des cartes (l'état n'est pas tronqué). Trop étroit : une ligne par colonne."""
    cols = t["colonnes"]; n = len(cols); total = w - 2 - (n - 1)
    def carte(x):
        """L'essentiel d'une carte : son titre (agent ou sujet court) et son état ; pas le titre du rôle ni la dernière action. Une validation ou une fusion garde son objet."""
        plat_ = [ANSI.sub("", ligne_texte(l)).lstrip("· ") for l in x["lignes"] if not ANSI.sub("", ligne_texte(l)).startswith("↳")]
        return phrase_patron(" · ".join([x["titre"]] + (plat_ if x["titre"].startswith(("validation", "fusion")) else plat_[-1:])), 200).replace("pas d'agent ouvert", "fermé")
    par = {c["cle"]: [x for x in t["cartes"] if x["colonne"] == c["cle"]] for c in cols}
    base = [len(f"{c['libelle']} ({len(par[c['cle']])})") + 1 for c in cols]
    if total < sum(base) + 8:
        return [couper(f"  {TONS[c['ton']]}{GRAS}{c['libelle']} ({len(par[c['cle']])}){R}" + (f" · {' · '.join(x['titre'] for x in par[c['cle']][:3])}" if par[c["cle"]] else f"{PALE} · rien{R}"), w) for c in cols]
    besoin = [max([base[i]] + [min(len(carte(x)) + 1, 34) for x in par[c["cle"]][:maxi]]) for i, c in enumerate(cols)]
    larg = base[:]; reste = total - sum(base)
    while reste > 0:                                                    # on remplit les colonnes qui en ont besoin, à parts égales
        ouvertes = [i for i in range(n) if larg[i] < besoin[i]]
        if not ouvertes: break
        part = max(1, reste // len(ouvertes))
        for i in ouvertes:
            ajout = min(part, besoin[i] - larg[i], reste); larg[i] += ajout; reste -= ajout
    haut = [" ".join(pad(TONS[c["ton"]] + GRAS + couper(f"{c['libelle']} ({len(par[c['cle']])})", larg[i]) + R, larg[i]) for i, c in enumerate(cols)),
            " ".join(TONS[c["ton"]] + "━" * larg[i] + R for i, c in enumerate(cols))]
    lignes = []
    for r in range(maxi):
        ligne = []
        for i, c in enumerate(cols):
            mes = par[c["cle"]]
            if r == maxi - 1 and len(mes) > maxi: ligne.append(pad(f"{PALE}… +{len(mes) - maxi + 1} autres{R}", larg[i]))
            else: ligne.append(pad(carte(mes[r]) if r < len(mes) else (f"{PALE}—{R}" if r == 0 else ""), larg[i]))
        if any(vlen(x.strip()) for x in ligne): lignes.append(" ".join(ligne))
    return ["  " + x for x in haut + lignes]


def alertes_compactes(al, w, rouges=None, jaunes=2):
    """Synthèse en tête de l'Accueil (31/10/2026) : le rouge puis le jaune, une ligne chacun avec « depuis quand » ; le reste est replié
    en « … et N autres » pour le JAUNE seulement : le ROUGE n'est jamais replié (01/11/2026), une alerte rouge doit rester visible. Rien à signaler : une seule ligne verte."""
    if not al: return [f"  {VERT}✓ rien en rouge ni en jaune{R}"]
    out = []
    for g, coul, maxi in (("rouge", ROUGE, rouges), ("jaune", JAUNE, jaunes)):
        mes = [x for x in al if x["gravite"] == g]
        for x in (mes if maxi is None else mes[:maxi]):
            q = datetime.datetime.fromisoformat(x["depuis"])
            out.append(couper(f"  {coul}●{R} {GRAS}{x['domaine']}{R}{coul} : {phrase_patron(x['texte'], 90)}{R}{PALE}  {'NOUVEAU · ' if x['nouveau'] else ''}depuis le {q:%d/%m %H:%M}{R}", w))
        if maxi is not None and len(mes) > maxi: out.append(couper(f"  {coul}●{R} {PALE}… et {len(mes) - maxi} autre{'s' if len(mes) - maxi > 1 else ''} en {g} · liste complète : page web, Accueil{R}", w))
    return out


def rendu_texte(d, w, h):
    """POSTE DE PILOTAGE (maquette A, 06/10/2026 ; refonte 30/10/2026) : EN HAUT les alertes (rouge et jaune, depuis quand), en gros ce qui attend
    le propriétaire — ou « Rien à faire » ; puis le Tableau compact, puis une ligne par agent. Sans défilement (≤ 42 lignes avec 7 agents) ; le détail est dans Décisions et À lire."""
    out = [INV + GRAS + pad(f" BERGER  ·  {d['agents_total']} agent{'s' if d['agents_total'] > 1 else ''}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    out += alertes_compactes(d["alertes"], w) + [""]
    toi = [x for x in d["attentes"] if x["pour"] == "toi"]; agent = [x for x in d["attentes"] if x["pour"] == "agent"]
    if not toi: out.append(f"  {VERT}{GRAS}✅ Rien à faire, tout avance{R}")
    else:
        out.append(f"  {ROUGE}{GRAS}⚠ {len(toi)} chose{'s' if len(toi) > 1 else ''} attend{'ent' if len(toi) > 1 else ''} ton geste{R}")
        for x in toi[:3]: out += ligne_attente(x, w)
        if len(toi) > 3: out.append(f"  {PALE}… {len(toi) - 3} autres · détail : Décisions{R}")
    if agent: out.append(f"  {PALE}{len(agent)} chose{'s' if len(agent) > 1 else ''} attend{'ent' if len(agent) > 1 else ''} un agent · détail : Décisions{R}")
    out += ["", PALE + "─" * w + R] + titre_section("TABLEAU", BLEU, w) + tableau_compact(d["tableau"], w)
    out += ["", PALE + "─" * w + R] + titre_section("AGENTS", BLEU, w)
    nomw = min(32, max(14, w // 4)); etatw = min(40, max(18, w // 3))
    for x in d["agents"]:
        ck = x["checklist"]; ag = x["agent"]
        cours = f"{plat(ck['titre'])[:50]} {ck['faites']}/{ck['total']}" if ck and not ck["fini"] else "—"
        statut = statuts_texte(x['statuts']).replace('?', 'état inconnu') or PALE + 'pas ouvert' + R
        out.append(couper(f"  {ag['icone']} {GRAS}{pad(ag['nom'], nomw)}{R} {pad(statut, etatw)} {cours}", w))
    for e in d["equipes"]:
        for m in e["membres"]:
            av = f"{m['faites']}/{m['total']}" if m["total"] is not None else "—"
            statut = statuts_texte(m['statuts']).replace('?', 'état inconnu') or PALE + 'pas ouvert' + R
            out.append(couper(f"  🔧 {GRAS}{pad(e['projet'] + ' · ' + m['sujet'], nomw)}{R} {pad(statut, etatw)} {av}" + (f"  {PALE}fusion : {m['demande']}{R}" if m["demande"] else ""), w))
    return out


def vue_accueil(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_accueil(w, h)
