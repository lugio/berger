#!/usr/bin/env python3
"""Refonte de l'espace Berger (30/10/2026) : Accueil et Décisions ne montrent comme « t'attend » QUE ce qui attend un geste du
propriétaire — sans modèle, avec un FAUX Herdr, dans une installation JETABLE.
Cas : rien en attente → « Rien à faire » ; une validation → ses deux commandes à copier ; le go d'un développeur → « attend un agent » ;
une ligne qui cite une écriture déjà décidée → masquée ; lectures réglées absentes ; propositions repliées ; Accueil ≤ 42 lignes avec 7
agents ; aucun chemin ni jargon ; regroupement des onglets 11 → 5 (31/10/2026) : Accueil (alertes + consommation), Décisions, Tableau, À lire,
Coulisses (4 panneaux) ; refaire-espace berger : ÉTAT FINAL des onglets ET des panneaux dans le faux Herdr, onglet de l'utilisateur gardé.
Usage : python3 tests/refonte-espace.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


net = lambda t: re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", t)

with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"; m.mkdir()
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}"); listes = m / "listes"; listes.mkdir()
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n[checklists]\ndossier = "{listes}"\n'
                                   f'[equipes.berger]\ndepot = "{m}/depot"\nchef_projet = "chef"\ncoordinateur = "coord"\nprefixe = "berger/"\n')
    journal = t / "herdr.log"; etat_onglets = t / "onglets.json"
    # faux Herdr À ÉTAT : onglets ET panneaux vivent dans un fichier ; `tab close`, `pane close`, `tab create` et `pane split` le changent vraiment
    # (on vérifie l'état FINAL, pas seulement les commandes). BERGER_FAUX_ACCUEIL = nombre de panneaux de l'onglet Accueil au départ.
    (t / "herdr").write_text("""#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]; E = %r; r = {}
open(%r, 'a').write(' '.join(a) + '\\n')
LIBELLES = ['🏠 Accueil', 'Livrables', 'Tableau', 'Synthèse', 'Sources', 'Décisions', 'À lire', 'Courtier', 'Échanges', 'Catalogue', 'Tokens',
            '🗂 Documents', '✅ Checklists', 'Notes Documents']
if not os.path.exists(E):
    tabs = [{'tab_id': 'w1:t%%d' %% (n + 1), 'label': l} for n, l in enumerate(LIBELLES)]
    panes = [{'pane_id': 'w1:p%%d' %% (k + 1), 'tab_id': 'w1:t1'} for k in range(int(os.environ.get('BERGER_FAUX_ACCUEIL', '2')))]
    panes += [{'pane_id': 'w1:p%%d' %% (len(panes) + n + 1), 'tab_id': x['tab_id']} for n, x in enumerate(tabs[1:])]
    json.dump({'tabs': tabs, 'panes': panes, 'n': 100}, open(E, 'w'))
S = json.load(open(E))
def sauver(): json.dump(S, open(E, 'w'))
def neuf(): S['n'] += 1; return S['n']
if a[:2] == ['workspace', 'list']: r = {'workspaces': [{'workspace_id': 'w1', 'label': 'Berger'}]}
elif a[:2] == ['tab', 'list']: r = {'tabs': S['tabs']}
elif a[:2] == ['tab', 'rename']:
    for x in S['tabs']:
        if x['tab_id'] == a[2]: x['label'] = a[3]
    sauver()
elif a[:2] == ['tab', 'close']:
    S['tabs'] = [x for x in S['tabs'] if x['tab_id'] != a[2]]; S['panes'] = [x for x in S['panes'] if x['tab_id'] != a[2]]; sauver()
elif a[:2] == ['tab', 'create']:
    label = a[a.index('--label') + 1]; n = neuf(); tid, pid = 'w1:t%%d' %% n, 'w1:p%%d' %% n
    S['tabs'].append({'tab_id': tid, 'label': label}); S['panes'].append({'pane_id': pid, 'tab_id': tid}); sauver()
    r = {'tab': {'tab_id': tid}, 'root_pane': {'pane_id': pid}}
elif a[:2] == ['pane', 'split']:
    de = next(x for x in S['panes'] if x['pane_id'] == a[a.index('--pane') + 1]); pid = 'w1:p%%d' %% neuf()
    S['panes'].append({'pane_id': pid, 'tab_id': de['tab_id']}); sauver(); r = {'pane': {'pane_id': pid}}
elif a[:2] == ['pane', 'close']: S['panes'] = [x for x in S['panes'] if x['pane_id'] != a[2]]; sauver()
elif a[:2] == ['pane', 'list']: r = {'panes': S['panes']}
elif a[:2] == ['pane', 'get']: r = {'pane': {'agent_status': 'idle'}}
print(json.dumps({'result': r}))
""" % (str(etat_onglets), str(journal))); os.chmod(t / "herdr", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(t / "herdr")}; env.pop("BERGER_HERDR_SOCKET", None)
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)
    noms = {"coord": "Coordinateur", "chef": "Chef", "veille": "Veille", "intendant": "Intendant", "dev-a": "Dev A", "dev-b": "Dev B", "dev-c": "Dev C"}
    for a, n in noms.items(): b("nouveau", a, n)
    for a in ("dev-a", "dev-b", "dev-c"):                                  # sept agents dont trois développeurs du projet berger
        f = i / "agents" / a / "agent.conf"; f.write_text(f.read_text() + f"projet = berger\nsujet = {a[-1]}\ncopie = {m}/copies/{a}\nbranche = berger/{a[-1]}\nport = 0\n")

    def checklist(a, texte): (i / "agents" / a / "CHECKLIST.md").write_text(texte)
    def rendu(vue, w=120, h=60):
        code = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
                f"print(json.dumps(g['VUES'][{vue!r}].rendre({w},{h})))")
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
        try: return [net(x) for x in json.loads(r.stdout.strip().splitlines()[-1])]
        except (ValueError, IndexError): return [f"ERREUR {r.stderr[-300:]}"]
    def onglets():
        code = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print(json.dumps([l for l,_ in g['ONGLETS_BERGER']]))")
        return json.loads(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120).stdout.strip().splitlines()[-1])
    texte = lambda vue, **k: "\n".join(rendu(vue, **k))
    def section(tx, deb, fin=None):
        reste = tx.split(deb, 1)[1] if deb in tx else ""
        return reste.split(fin, 1)[0] if fin else reste

    # ── 1. rien n'attend le propriétaire
    acc = texte("accueil"); dec = texte("decisions")
    dire("Rien à faire, tout avance" in acc, "Accueil sans rien en attente : « Rien à faire, tout avance »")
    dire("Rien à faire, tout avance" in dec and "T'ATTEND (0)" in dec, "Décisions sans rien en attente : « Rien à faire », T'ATTEND (0)")

    # ── 2. un seul Accueil, ≤ 42 lignes avec 7 agents, Tableau compact en 5 colonnes
    dire(sum(1 for l in rendu("accueil") if "BERGER  ·" in l) == 1, "un seul Accueil dans le rendu (un seul bandeau)")
    dire(len(rendu("accueil", 120, 40)) <= 42 and "7 agents" in acc, f"Accueil : {len(rendu('accueil', 120, 40))} lignes (≤ 42) avec 7 agents")
    ent = next((l for l in rendu("accueil") if "EN COURS" in l), "")
    dire(all(c in ent for c in ("EN COURS", "ATTEND PROPRIO", "ATTEND UN AGENT", "AU REPOS", "LIVRÉ")), f"Tableau compact : les 5 colonnes gardées (obtenu {ent.strip()[:120]})")
    dire(acc.index("Rien à faire") < acc.index("TABLEAU") < acc.index("AGENTS"), "Accueil : ce qui attend, puis le Tableau, puis les agents")

    checklist("veille", "# Rôle de veille permanente du projet berger et de ses lots\n- [x] a\n- [ ] b\n")
    cmp_ = section(texte("accueil"), "TABLEAU", "AGENTS")
    dire("Rôle de veille" not in cmp_ and "Chef" in cmp_ and "Coordinateur" in cmp_, "Tableau compact : l'agent (et son état), pas le titre de son rôle")
    checklist("veille", "")
    dire(not re.search(r"\S…", cmp_) and "○ fermé" in cmp_, f"Tableau compact : l'état des cartes n'est pas tronqué (colonnes vides étroites, colonnes pleines larges) : {[l.strip() for l in cmp_.splitlines() if '…' in l][:2]}")

    # ── 3. une validation en attente : ses deux commandes prêtes à copier
    v = i / "courtier/validations"; v.mkdir(parents=True, exist_ok=True)
    (v / "7.json").write_text(json.dumps({"n": 7, "agent": "veille", "outil": "essai", "verbe": "ecrire", "apercu": "couper le compte de test", "demande": "2026-10-30T09:00:00"}))
    acc = texte("accueil"); dec = texte("decisions")
    dire("berger valider 7" in acc and "berger refuser 7" in acc and "Rien à faire" not in acc, "Accueil : la validation n° 7 avec berger valider 7 / berger refuser 7")
    dire("berger valider 7" in section(dec, "T'ATTEND", "ATTEND UN AGENT") and "couper le compte de test" in dec, "Décisions : la validation n° 7 dans T'ATTEND, avec ses deux commandes")
    dire(len(rendu("accueil", 120, 40)) <= 42, "Accueil avec une validation : toujours ≤ 42 lignes")
    (v / "7.json").unlink()

    # ── 4. le go attendu d'un développeur attend son chef : « attend un agent », pas « t'attend »
    checklist("dev-a", "# Travail\n- [ ] étape\n⚠ Go attendu : feu vert du chef pour pousser la demande — a-lire/2026-10-30_lot.md\n")
    dec = texte("decisions"); acc = texte("accueil")
    dire("feu vert du chef" in section(dec, "ATTEND UN AGENT") and "feu vert du chef" not in section(dec, "T'ATTEND", "ATTEND UN AGENT"),
         "go attendu d'un développeur : dans ATTEND UN AGENT, pas dans T'ATTEND")
    dire("Rien à faire, tout avance" in acc, "Accueil : le go d'un développeur ne compte pas comme un geste du propriétaire")
    dire("a-lire/" not in acc + dec and ".md" not in acc + dec, "aucun chemin a-lire/ ni .md dans Accueil et Décisions")
    checklist("coord", "# Coordination\n- [ ] étape\n⚠ Go attendu : lancer le lot 2\n")                       # un agent qui rend compte au propriétaire
    dec = texte("decisions")
    dire("lancer le lot 2" in section(dec, "T'ATTEND", "ATTEND UN AGENT") and "Rien à faire" not in section(dec, "T'ATTEND", "ATTEND UN AGENT"), "go d'un coordinateur : dans T'ATTEND")
    checklist("coord", "# Coordination\n- [ ] étape\n❓ Question : on garde la recette ?\n")
    dire("on garde la recette" in section(texte("decisions"), "T'ATTEND", "ATTEND UN AGENT"), "question d'un agent qui rend compte au propriétaire : dans T'ATTEND")
    checklist("coord", "")

    # ── 5. renvoi n° 109 (B1) : plus aucune ligne de checklist n'est masquée en devinant dans son TEXTE ; seule une convention structurée
    #      (« Lié à : validation <n> » d'un document À lire, « Décision liée : … ») règle quelque chose
    (v / "101.fait.json").write_text(json.dumps({"n": 101, "etat": "refusé"}))
    checklist("chef", "# Relecture\n- [ ] étape\n⚠ Bloqué : fusion n° 101 (web intégré) attend sa décision\n")
    dire("fusion n° 101" in texte("decisions"), "blocage qui cite l'écriture n° 101 décidée : toujours affiché (aucun masquage par le texte)")
    checklist("coord", "# Coordination\n- [ ] étape\n⚠ Go attendu : validation n° 101 refusée : autoriser une nouvelle tentative ?\n")
    dire("autoriser une nouvelle tentative" in section(texte("decisions"), "T'ATTEND", "ATTEND UN AGENT"), "« Go attendu : validation n° 101 refusée : autoriser une nouvelle tentative ? » reste affiché")
    checklist("coord", "# Coordination\n- [ ] étape\n❓ Question : Après le refus n° 101, faut-il préparer une autre solution ?\n")
    dire("préparer une autre solution" in section(texte("decisions"), "T'ATTEND", "ATTEND UN AGENT"), "nouvelle question qui cite le refus n° 101 : affichée")
    (i / "agents/coord/a-lire").mkdir(exist_ok=True)
    (i / "agents/coord/a-lire/2026-10-30_decision.md").write_text("# Rapport\nDécision attendue : autoriser une nouvelle tentative après le refus n° 101\n")
    dire("autoriser une nouvelle tentative après" in section(texte("decisions"), "T'ATTEND", "ATTEND UN AGENT"), "« Décision attendue » qui cite l'écriture n° 101 décidée : affichée")
    (i / "agents/coord/a-lire/2026-10-30_decision.md").write_text("# Rapport\nDécision attendue : autoriser une nouvelle tentative après le refus n° 101\nDécision liée : validation:101\n")
    dire("autoriser une nouvelle tentative après" not in texte("decisions"), "« Décision liée : validation:101 » (convention structurée) décidée : réglée")
    (i / "agents/coord/a-lire/2026-10-30_decision.md").unlink(); checklist("coord", ""); checklist("chef", "")

    # ── 6. lectures : seulement dans À lire, les réglées retirées, jamais comptées comme décisions
    (i / "agents/veille/a-lire").mkdir(exist_ok=True)
    (i / "agents/veille/a-lire/2026-10-30_rapport.md").write_text("# Rapport à lire\n")
    (i / "agents/veille/a-lire/2026-10-30_regle.md").write_text("# Rapport déjà réglé\nLié à : validation 101\n")
    al = texte("alire"); dec = texte("decisions"); acc = texte("accueil")
    dire("Rapport à lire" in al and "Rapport déjà réglé" not in al, "À lire : la lecture à faire y est, la lecture réglée est retirée")
    dire("Rapport à lire" not in dec + acc and "lecture" not in (dec + acc).lower().replace("décisions", ""), "Décisions et Accueil : aucune lecture comptée comme décision")
    dire("Rien à faire, tout avance" in acc, "Accueil : des lectures non lues ne rompent pas « Rien à faire »")
    (i / "agents/veille/a-lire/2026-10-31_urgent.md").write_text("# Rapport urgent\nCorps urgent unique\n")          # le plus récent : numéro 1 une fois la lecture réglée retirée
    os.utime(i / "agents/veille/a-lire/2026-10-31_urgent.md", (4102444800, 4102444800))
    al = rendu("alire"); n_urgent = next((int(re.search(r"●\s+(\d+)\s", l).group(1)) for l in al if "Rapport urgent" in l), None)
    n_autre = next((int(re.search(r"[●✓]\s+(\d+)\s", l).group(1)) for l in al if "Rapport à lire" in l), None)
    o1 = b("lire", str(n_urgent), "--sans-pager"); o2 = b("lire", str(n_autre), "--sans-pager")
    dire(n_urgent is not None and "Corps urgent unique" in o1.stdout and "Rapport à lire" in net(o2.stdout), f"À lire : le numéro affiché ouvre CE document-là (urgent n° {n_urgent}, autre n° {n_autre})")

    # ── 7. propositions : un bloc à part, replié
    (i / "agents/veille/pending").mkdir(exist_ok=True)
    (i / "agents/veille/pending/2026-10-30_sujet.md").write_text("type: memoire\npourquoi: x\n---\nTexte\n")
    dec = texte("decisions")
    dire("PROPOSITIONS (1)" in dec and "repliées" in dec and "T'ATTEND (0)" in dec, "propositions : bloc replié à part, absentes de T'ATTEND")
    (i / "agents/veille/pending/2026-10-30_sujet.md").unlink()

    # ── 8. Regroupement des onglets, 11 → 5 (31/10/2026) : Accueil · Décisions · Tableau · À lire · Coulisses
    CINQ = ["Décisions", "Tableau", "À lire", "Coulisses"]
    dire(onglets() == CINQ, f"onglets après l'Accueil : Décisions, Tableau, À lire, Coulisses (obtenu {onglets()})")
    pan = lambda: json.loads(subprocess.run([sys.executable, "-c", f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');print(json.dumps(g['PANNEAUX_BERGER']))"],
                                            env=env, capture_output=True, text=True, timeout=120).stdout.strip().splitlines()[-1])
    p = pan()
    dire(p["Accueil"] == ["accueil", "tokens"] and p["Coulisses"] == ["courtier", "echanges", "sources", "catalogue"] and p["À lire"] == ["alire"]
         and p["Tableau"] == ["colonnes"], f"panneaux : Accueil + consommation, Coulisses = Courtier, Échanges, Sources, Catalogue (obtenu {p})")
    dire(all(len(v) <= 4 for v in p.values()) and "Livrables" not in p and "Synthèse" not in p, "4 panneaux au plus par onglet ; ni Livrables ni Synthèse en onglet")
    (listes / "feuille.md").write_text("# Feuille\n- [ ] à faire\n")
    dire(onglets() == CINQ and pan()["Tableau"] == ["colonnes", "checklists"], "une liste ouverte : pas d'onglet de plus, un second panneau dans Tableau")
    (listes / "feuille.md").write_text("# Feuille\n- [x] fait\n")
    dire(pan()["Tableau"] == ["colonnes"], "liste entièrement cochée : plus de panneau Checklists")
    (i / "commun").mkdir(exist_ok=True)
    dire(rendu("alire") and all(isinstance(x, str) for x in rendu("alire")), "À lire se rend toujours (liste de chaînes)")
    al = rendu("accueil")
    dire(len(al) > 1 and any("depuis le" in x for x in al[:12]) or any("rien en rouge ni en jaune" in x for x in al[:6]), "Accueil : les alertes (avec « depuis le ») en tête")
    # Aucune alerte ROUGE perdue (correctif 01/11/2026, relecture n° 119) : 4 rouges + 3 jaunes → les 4 rouges toutes lisibles
    ac = json.loads(subprocess.run([sys.executable, "-c", f"import runpy,sys,json,re;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
        "al=[{'gravite':'rouge' if k<4 else 'jaune','domaine':f'dom{k}','texte':f'probleme-{k}','depuis':'2026-10-30T08:00:00','nouveau':False} for k in range(7)];"
        "print(json.dumps([re.sub(r'\\x1b\\[[0-9;]*m','',l) for l in g['VUES']['accueil'].alertes_compactes(al,120)]))"],
        env=env, capture_output=True, text=True, timeout=120).stdout.strip().splitlines()[-1])
    dire(all(any(f"probleme-{k}" in l for l in ac) for k in range(4)), f"Accueil : 4 alertes rouges, les 4 sont affichées ({len(ac)} lignes)")
    dire(any("autre" in l and "jaune" in l for l in ac) or all(any(f"probleme-{k}" in l for l in ac) for k in range(4, 7)), "Accueil : les jaunes en trop sont comptées (« … et N autre(s) en jaune »)")

    # ── 9. refaire-espace berger : l'ÉTAT FINAL du faux Herdr (onglets ET panneaux), deux départs
    commandes = lambda: [" ".join(l.split()[3:]) for l in journal.read_text().splitlines() if l.startswith("pane run")]
    def etat(): return json.loads(etat_onglets.read_text())
    def panneaux_de(label):
        S_ = etat(); tid = next(x["tab_id"] for x in S_["tabs"] if x["label"] == label)
        return [x["pane_id"] for x in S_["panes"] if x["tab_id"] == tid]
    for depart in ("3", "1"):                                              # 3 panneaux dans l'Accueil (un en trop) · 1 seul (il manque la consommation)
        for f in (etat_onglets, journal):
            if f.exists(): f.unlink()
        env["BERGER_FAUX_ACCUEIL"] = depart
        r = b("refaire-espace", "berger"); log = journal.read_text() if journal.exists() else ""; S_ = etat(); final = [x["label"] for x in S_["tabs"]]
        dire(r.returncode == 0, f"refaire-espace berger (Accueil à {depart} panneau(x)) : code 0 ({r.stderr.strip()[-160:]})")
        dire(sorted(final) == sorted(["🏠 Accueil", "🔔 Décisions", "📋 Tableau", "📖 À lire", "⚙ Coulisses", "Notes Documents"]),
             f"ÉTAT FINAL ({depart}) : 5 onglets + l'onglet personnalisé « Notes Documents » gardé — Livrables, Synthèse, Sources, Courtier, Échanges, Catalogue, Tokens, Documents, Checklists retirés (obtenu {final})")
        dire(len(panneaux_de("🏠 Accueil")) == 2, f"ÉTAT FINAL ({depart}) : l'Accueil a exactement 2 panneaux, accueil et consommation ({panneaux_de('🏠 Accueil')})")
        dire(len(panneaux_de("⚙ Coulisses")) == 4, f"ÉTAT FINAL ({depart}) : Coulisses a 4 panneaux ({panneaux_de('⚙ Coulisses')})")
        cmds = [l.split("; ", 1)[-1] for l in log.splitlines() if l.startswith("pane run")]
        dire(sum(c.endswith("panneau accueil") for c in cmds) == 1 and sum(c.endswith("panneau tokens") for c in cmds) == 1,
             f"({depart}) l'Accueil lance accueil puis tokens, une fois chacun")
        dire([c.rsplit(" ", 1)[-1] for c in cmds if c.rsplit(" ", 1)[-1] in ("courtier", "echanges", "sources", "catalogue")] == ["courtier", "echanges", "sources", "catalogue"],
             f"({depart}) Coulisses lance ses quatre panneaux dans l'ordre")

print(f"\n{'tout passe' if not ko else f'{ko} échec(s)'}")
sys.exit(1 if ko else 0)
