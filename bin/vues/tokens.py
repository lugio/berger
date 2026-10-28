# Vue « Tokens » de Berger : berger panneau tokens. Déplacée telle quelle depuis bin/berger (07/10/2026) ; le cœur la découvre
# par son nom de fichier. Les fonctions du cœur (conf, lire, herdr, cadre…) sont disponibles ici comme là-bas.
# Données et rendu séparés (spec interface, 13/10/2026) : donnees() → tokens.schema.json ; rendu_texte() ne lit que ces données.
TITRE = "Tokens"
ICONE = '🪙'
ONGLET = "berger"     # "berger" : onglet de l'espace Berger (ORDRE après l'Accueil) ; "agent" : vue d'un agent, sans onglet propre
ORDRE = 10


def donnees(a=None):
    """Quota de chaque moteur et consommation par agent et par moteur (journaux locaux, lecture seule). Seuils : quota ≥ 95 %
    rouge, ≥ 80 % jaune ; contexte relu ≥ 800 k rouge, ≥ 500 k jaune."""
    evts = collecter_conso(); maint = time.time()
    debut_j = datetime.datetime.combine(datetime.date.today(), datetime.time()).timestamp()
    moteurs = sorted(set(LECTEURS_CONSO) & ({conf(x).get("moteur") for x in agents()} | {e["m"] for e in evts}) or set(LECTEURS_CONSO))
    def remise(r):
        try: return datetime.datetime.fromtimestamp(float(r)).isoformat(timespec="seconds")
        except (TypeError, ValueError): return None
    quotas = []
    for m, v in sorted(quota_moteurs().items()):
        if m not in moteurs: continue
        mesure = bool(v and v[0])
        quotas.append({"moteur": m, "mesure": mesure, "age_min": int(v[1] // 60) if mesure else None,
                       "fenetres": [{"nom": n, "pourcent": p, "ton": "rouge" if p >= 95 else "jaune" if p >= 80 else "vert", "remise": remise(r)}
                                    for n, p, r in v[0]] if mesure else []})
    par = {}
    for e in evts: par.setdefault((e["a"], e["m"]), []).append(e)
    agents_ = []
    for (x, m), es in sorted(par.items()):
        if x not in agents(): continue
        auj = [e for e in es if e["t"] >= debut_j]; der = max(es, key=lambda e: e["t"])
        agents_.append({"agent": agent_court(x), "moteur": m, "auj_lus": sum(e["lus"] for e in auj), "auj_ecrits": sum(e["ecr"] for e in auj),
                        "sept_j_lus": sum(e["lus"] for e in es), "sept_j_ecrits": sum(e["ecr"] for e in es), "contexte": der["ctx"],
                        "ton_contexte": "rouge" if der["ctx"] >= 800_000 else "jaune" if der["ctx"] >= 500_000 else None,
                        "derniere": quand_iso(der["t"]), "il_y_a_min": int((maint - der["t"]) // 60), "modele": der["mod"]})
    return {"quotas": quotas, "par_agent": agents_, "sources": sorted(LECTEURS_CONSO)}


def rendu_texte(d, w, h):
    """TOKENS : quota de chaque moteur et consommation par agent et par moteur (journaux locaux, lecture seule)."""
    out = [INV + GRAS + pad(" TOKENS  ·  par moteur et par agent", w - 7) + f"{datetime.datetime.now():%H:%M}  " + R, ""]
    out += titre_section("QUOTA DES ABONNEMENTS", BLEU, w)
    for q in d["quotas"]:
        m = q["moteur"]
        if not q["mesure"]:
            out.append(f"  {m:<7} {PALE}non mesuré — " + ("une passerelle qui ne relaie pas les en-têtes d'Anthropic, ou aucune réponse encore"
                                                             if m == "claude" else "aucune session récente") + R); continue
        out.append(f"  {m:<7} " + f"{PALE} · {R}".join(
            f"{TONS[f['ton']]}{'⚠ ' if f['ton'] != 'vert' else ''}{f['nom']} {f['pourcent']:.0f} %{R} {PALE}→ "
            f"{quand_remise(datetime.datetime.fromisoformat(f['remise']).timestamp()) if f['remise'] else '?'}{R}" for f in q["fenetres"])
            + f"  {PALE}(il y a {q['age_min']} min){R}")
    out += [""] + titre_section("PAR AGENT  (lus = entrée + cache · écrits)", CYAN, w)
    if w >= 100: out.append(f"  {PALE}{pad('agent', 16)}{pad('moteur', 8)}{pad('auj. lus/écrits', 18)}{pad('7 j lus/écrits', 18)}{pad('contexte', 10)}dernière{R}")
    for x in d["par_agent"]:
        c = TONS[x["ton_contexte"]] if x["ton_contexte"] else ""
        if w < 100:
            out += [couper(f"  {x['agent']['icone']} {x['agent']['nom']} · {x['moteur']} · il y a {x['il_y_a_min']} min", w),
                    couper(f"    auj. {kilo(x['auj_lus'])}/{kilo(x['auj_ecrits'])} · 7 j {kilo(x['sept_j_lus'])}/{kilo(x['sept_j_ecrits'])} · contexte {c}{kilo(x['contexte'])}{R}", w)]
            out += plier(x['modele'], w, '    modèle : ', '             ', PALE)
            continue
        out.append(f"  {pad(x['agent']['icone'] + ' ' + x['agent']['nom'], 16)}{pad(x['moteur'], 8)}"
                   f"{pad(kilo(x['auj_lus']) + ' / ' + kilo(x['auj_ecrits']), 18)}"
                   f"{pad(kilo(x['sept_j_lus']) + ' / ' + kilo(x['sept_j_ecrits']), 18)}"
                   f"{c}{pad(kilo(x['contexte']), 10)}{R if c else ''}{PALE}il y a {x['il_y_a_min']} min · {x['modele']}{R}")
    if not d["par_agent"]: out.append(PALE + "  aucune réponse ces 7 derniers jours" + R)
    out += ["", f"  {PALE}source : journaux locaux de chaque moteur ({', '.join(d['sources'])}) · aucun coût en euros (pas de tarif codé){R}"]
    # Les quotas et leur échéance sont variables : les replier aussi, sans perdre la fin de la ligne.
    return [ligne for l in out for ligne in (plier(ANSI.sub('', l), w, '  ', '  ') if vlen(l) > w else [l])]


def vue_tokens(w, h):
    return rendu_texte(donnees(), w, h)


def rendre(w, h, a=None):
    return vue_tokens(w, h)
