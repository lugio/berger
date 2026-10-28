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
    return {"agents_total": len(agents()),
            "a_toi": [d for d in att if not d["valideur"]], "delegues": [d for d in att if d["valideur"]],
            "bloques": [{"agent": agent_court(x), "bloque": checklist(x)["bloque"]} for x in agents() if (checklist(x) or {}).get("bloque")],
            "a_lire": [{"id": id_document(d), "titre": d["titre"]} for d in documents_a_lire() if d["cle"] not in vus],
            "agents": [{"agent": agent_court(x), "statuts": statuts_donnees(x), "checklist": checklist_donnees(checklist(x)),
                        "derniere_action": derniere_action(x)} for x in agents() if x not in devs],
            "equipes": equipes, "attentes": decisions()}


def rendu_texte(d, w, h):
    """POSTE DE PILOTAGE (maquette A, 06/10/2026 ; NN/g « Dashboards » et « Progressive Disclosure ») : d'un coup d'œil,
    EN HAUT ce qui attend le propriétaire, puis une ligne par agent et par équipe. Le détail est dans l'espace de chacun."""
    out = [INV + GRAS + pad(f" BERGER  ·  {d['agents_total']} agent{'s' if d['agents_total'] > 1 else ''}", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    attentes = d["attentes"]; a_toi = [x for x in attentes if x["pour"] == "toi"]; bloques = d["bloques"]
    out += titre_section(f"À TOI DE DÉCIDER ({len(a_toi)})", ROUGE if a_toi else VERT, w)
    categories = {}
    for x in a_toi: categories[x['genre']] = categories.get(x['genre'], 0) + 1
    libelles = {'validation': ('écriture', 'écritures'), 'bloque': ('blocage', 'blocages'),
                'proposition': ('proposition', 'propositions'), 'signalement': ('signalement', 'signalements'),
                'terminal': ('réponse au terminal', 'réponses au terminal'), 'a_lire': ('lecture', 'lectures'),
                'a_decider': ('décision de rapport', 'décisions de rapport'), 'fusion': ('fusion', 'fusions'),
                'go': ('go', 'go'), 'question': ('question', 'questions')}
    if categories: out += plier(" · ".join(f"{n} {libelles[g][n > 1]}" for g, n in categories.items()), w, "  ", "  ")
    for x in a_toi[:3]:
        out += plier(f"{x['titre']} : {x['detail']}", w - 2, f"  {ROUGE}●{R} ", "    ")
    if len(a_toi) > 3: out.append(f"  {PALE}… {len(a_toi) - 3} autres · détail : Décisions{R}")
    if not a_toi: out.append(PALE + "  rien" + R)
    delegues = [x for x in attentes if x['pour'] == 'agent']
    out.append(f"  {PALE}Attend un agent : {len(delegues)} · détail : Décisions{R}")
    out += [""] + titre_section(f"BLOQUÉ ({len(bloques)})", JAUNE if bloques else VERT, w)
    for x in bloques: out += plier(plat(x["bloque"]), w - 2, f"  {JAUNE}●{R} {GRAS}{x['agent']['nom']}{R} : ", "      ")
    if not bloques: out.append(PALE + "  rien" + R)
    if d["a_lire"]:
        out += [""] + titre_section(f"📖 À LIRE ({len(d['a_lire'])})", JAUNE, w)
        for x in d["a_lire"][:3]: out.append(couper(f"  {JAUNE}●{R} {x['titre']}  {PALE}→ onglet À lire{R}", w))
    out += ["", PALE + "─" * w + R] + titre_section("AGENTS", BLEU, w)
    for x in d["agents"]:
        ck = x["checklist"]; ag = x["agent"]
        cours = f"{plat(ck['titre'])[:40]} {ck['faites']}/{ck['total']}" if ck and not ck["fini"] else "—"
        statut = statuts_texte(x['statuts']).replace('?', 'état inconnu') or PALE + 'pas ouvert' + R
        nomw = min(20, max(12, w // 7)); etatw = min(46, max(24, w // 3))
        if vlen(statut) > etatw or w < 100:
            out.append(couper(f"  {ag['icone']} {GRAS}{ag['nom']}{R} · {cours}", w))
            out += plier(ANSI.sub('', statut), w, '    ', '    ', PALE)
            continue
        ligne = f"  {ag['icone']} {GRAS}{pad(ag['nom'], nomw)}{R} {pad(statut, etatw)} "
        out.append(ligne + pad(cours, max(0, w - vlen(ligne))))
        if x['derniere_action'] and w >= 120: out.append(couper(f"    {PALE}↳ {x['derniere_action']}{R}", w))
    for e in d["equipes"]:
        out += [""] + titre_section(f"Équipe {e['projet']}", CYAN, w)
        for m in e["membres"]:
            av = f"{m['faites']}/{m['total']}" if m["total"] is not None else "—"
            statut = statuts_texte(m['statuts']).replace('?', 'état inconnu') or 'pas ouvert'
            out.append(couper(f"  🔧 {GRAS}{m['sujet']}{R} · {statut} · {av}", w))
            out.append(couper(f"     {PALE}demande de fusion : {m['demande'] or 'aucune'}{R}", w))
        if e["fusionnes"]:
            out += plier(f"fusionnés ({len(e['fusionnes'])}) : {', '.join(e['fusionnes'][-3:][::-1])}", w, "  ", "    ", PALE)
        if not e["membres"] and not e["fusionnes"]: out.append(PALE + "  aucun développeur ouvert" + R)
    return out


def vue_accueil(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_accueil(w, h)
