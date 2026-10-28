#!/usr/bin/env python3
"""Test de contrat des vues (bin/vues/<type>.py) — sans modèle, avec un FAUX Herdr, dans une installation JETABLE : chaque vue
porte TITRE, ICONE, ONGLET, ORDRE et rendre(w, h, a=None) qui rend une liste de lignes (cadre() les ajuste au pane) ; les onglets de l'espace Berger et
leurs icônes viennent des vues (plus rien en dur) ; une vue PIÉGÉE (fichier cassé, constante manquante) est écartée et NOMMÉE
(berger etat, berger panneau), les autres s'affichent. Usage : python3 tests/vues.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import json, os, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n')
    (t / "herdr").write_text("#!/bin/sh\necho '{\"result\": {}}'\n"); os.chmod(t / "herdr", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(t / "herdr")}
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)
    b("nouveau", "vigie", "Vigie")                                          # une vue d'agent a besoin d'un agent

    def charge():
        code = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
                "V=g['VUES'];out={}\n"
                "for n,v in V.items():\n"
                "  if v.ONGLET == 'objet': continue\n"
                "  try: l=v.rendre(80,24,'vigie'); out[n]=l if isinstance(l,list) and all(isinstance(x,str) for x in l) else repr(l)[:80]\n"
                "  except Exception as e: out[n]='ERREUR '+type(e).__name__+': '+str(e)[:80]\n"
                "print(json.dumps({'vues':{n:[v.TITRE,v.ICONE,v.ONGLET,v.ORDRE] for n,v in V.items()},'refusees':g['VUES_REFUSEES'],"
                "'onglets':list(g['ONGLETS_BERGER']),'icones':g['ICONES_ONGLETS'],'rendu':out,'vue_x':[k for v in V.values() for k in vars(v) if k.startswith('vue_')],'vue_coeur':[k for k in g if k.startswith('vue_')]}))")
        r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
        try: return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): sys.exit(f"ARRÊT : le cœur ne charge pas — {r.stderr[-400:]}")

    g = charge(); vues = g["vues"]
    fichiers = sorted(p.stem for p in (SRC / "bin/vues").glob("*.py") if not p.name.startswith("_"))
    dire(sorted(vues) == fichiers and not g["refusees"], f"chaque fichier de bin/vues/ est une vue chargée ({len(vues)}), aucune écartée (obtenu {sorted(vues)}, écartées {g['refusees']})")
    dire(all(isinstance(v[0], str) and v[0] and (v[1] is None or (isinstance(v[1], str) and len(v[1]) == 1)) and v[2] in ("berger", "agent", "objet")
             and isinstance(v[3], int) for v in vues.values()), f"contrat : TITRE texte, ICONE un caractère ou None, ONGLET berger|agent|objet, ORDRE entier ({vues})")
    mauvais = {n: r for n, r in g["rendu"].items() if not isinstance(r, list)}
    dire(not mauvais, f"rendre(80, 24, agent) : chaque vue rend une liste de chaînes, sans erreur (fautives : {mauvais})")
    # la largeur n'est PAS exigée des vues : c'est cadre() qui coupe et replie à la taille du pane (tests/affichage.py)
    attendu = [["Livrables", "livrables"], ["Documents", "documents"], ["Tableau", "colonnes"], ["Synthèse", "synthese"], ["Sources", "sources"], ["Décisions", "decisions"], ["Checklists", "checklists"],
               ["À lire", "alire"], ["Courtier", "courtier"], ["Échanges", "echanges"], ["Catalogue", "catalogue"], ["Tokens", "tokens"]]
    dire(g["onglets"] == attendu, f"ONGLETS_BERGER vient des vues (ONGLET = berger, triées par ORDRE, Accueil à part) (obtenu {g['onglets']})")
    dire(all(g["icones"].get(v[0]) == v[1] for v in vues.values() if v[2] == "berger") and g["icones"].get("Travail") == "💼",
         "ICONES_ONGLETS : icône de chaque onglet de vue + celles des onglets fixes (Travail, Fiche, Missions, Équipe)")
    dire(all(f"vue_{n}" in g["vue_x"] or n == "fiche" or vues[n][2] == "objet" for n in vues) and "vue_fiche_page" in g["vue_x"],
         "les fonctions vue_<nom> restent appelables par le registre VUES (lire_interactif, tests existants)")
    dire(g["vue_coeur"] == [], "modulaire lot 1 : plus aucune fonction vue_<nom> dans les globales du cœur (accès par VUES[\"<type>\"])")
    r = b("etat"); dire(r.returncode == 0 and "vue écartée" not in r.stdout, "berger etat : rien à signaler quand toutes les vues chargent")

    # vues piégées : un fichier cassé, une sans rendre → écartées, nommées ; les autres s'affichent
    (i / "bin/vues/piege.py").write_text("TITRE = 'Piège'\nICONE = '💣'\nONGLET = 'berger'\nORDRE = 99\ndef rendre(w, h, a=None)  # syntaxe cassée\n")
    (i / "bin/vues/muette.py").write_text("TITRE = 'Muette'\nICONE = '🔇'\nONGLET = 'berger'\nORDRE = 98\n")
    g2 = charge()
    dire(set(g2["refusees"]) == {"piege", "muette"} and "SyntaxError" in g2["refusees"]["piege"] and "rendre" in g2["refusees"]["muette"],
         f"deux vues piégées écartées et nommées avec la cause (obtenu {g2['refusees']})")
    dire(sorted(g2["vues"]) == fichiers and g2["onglets"] == attendu and "Piège" not in g2["icones"],
         "les autres vues chargent toujours ; les onglets et icônes ne voient pas les vues écartées")
    dire(all(isinstance(r, list) for r in g2["rendu"].values()), "les autres vues s'affichent toujours")
    r = b("etat"); dire(r.returncode == 0 and "vue écartée : bin/vues/piege.py" in r.stdout and "bin/vues/muette.py" in r.stdout,
                        f"berger etat nomme les vues écartées (code {r.returncode})")
    r = b("panneau", "piege"); dire(r.returncode != 0 and "piege" in (r.stderr + r.stdout) and "SyntaxError" in (r.stderr + r.stdout),
                                    f"berger panneau piege : refus nommé, avec la cause (code {r.returncode})")
    r = b("panneau", "inconnue"); dire(r.returncode != 0 and "vue inconnue" in (r.stderr + r.stdout) and "accueil" in (r.stderr + r.stdout),
                                       "berger panneau <inconnue> : refus, avec la liste des vues")

print(f"---- {ko} échec(s)"); sys.exit(1 if ko else 0)
