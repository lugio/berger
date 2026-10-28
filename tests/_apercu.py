#!/usr/bin/env python3
"""Aperçu STATIQUE de l'interface (docs/apercu/interface.html) : la vraie page (bin/page/app.js et app.css, tels quels) avec, à la
place du serveur, une petite fonction qui répond depuis le JEU DE DONNÉES DES TESTS (tests/_jeu_vues.py, agents fictifs) —
sans réseau ni jeton : le fichier s'ouvre dans un navigateur, sur PC comme sur téléphone. Pour montrer le rendu au
propriétaire AVANT une fusion. Usage : python3 tests/_apercu.py  (réécrit docs/apercu/interface.html)"""
import json, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _jeu_vues as J

SRC = Path(__file__).resolve().parent.parent
SORTIE = SRC / "docs/apercu/interface.html"

with tempfile.TemporaryDirectory() as t:
    i, env = J.construire(t, marquages=True); objets = J.objets(i, env)
    b = lambda *a: json.loads(J.commande(i, env, *a).stdout.replace(str(i.parent), "~"))   # dossier jetable → « ~ »
    reponses = {"/api/vues": b("vues", "--json"), "/api/etat": b("etat", "--json"), "/api/validations": b("validations", "--json")}
    for d in ("bin/vues", "bin/schemas"):
        for p in (SRC / d).glob("*.schema.json"): reponses["/api/schema/" + p.name[:-len(".schema.json")]] = json.loads(p.read_text())
    for v in reponses["/api/vues"]["vues"]:
        if not v["donnees"]: continue
        args = J.AGENTS_JEU if v["onglet"] == "agent" else objets.get(v["type"], []) if v["onglet"] == "objet" else [None]
        for a in args:
            reponses["/api/vue/" + v["type"] + (f"?a={a}" if a else "")] = b("vue", v["type"], *([a] if a else []), "--json")

page = (SRC / "bin/page/index.html").read_text()
# Bandeau de l'aperçu (hors de la page) : il dit que les données sont fictives, et bascule clair / sombre / système.
BANDEAU = ('<div id="apercu" style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;padding:.4rem 1rem;background:#1f2937;color:#f9fafb;'
           'font:13px system-ui">APERÇU — données d\'exemple (agents fictifs), aucune donnée réelle, aucune connexion. '
           '<span style="margin-left:auto">Thème :</span>'
           + "".join(f'<button type="button" data-theme-apercu="{v}" style="font:inherit;padding:.15rem .6rem;border:1px solid #4b5563;'
                     f'border-radius:4px;background:#111827;color:#f9fafb;cursor:pointer">{l}</button>'
                     for v, l in (("clair", "Clair"), ("sombre", "Sombre"), ("", "Système"))) + "</div>")
BASCULE = ("document.addEventListener('click', e => { const b = e.target.closest('[data-theme-apercu]'); if (!b) return;\n"
           "  const v = b.getAttribute('data-theme-apercu'); if (v) document.documentElement.dataset.theme = v; else delete document.documentElement.dataset.theme; });\n")
serveur = (BASCULE + "// Aperçu : pas de serveur ; chaque adresse /api/… répond depuis le jeu de données des tests (agents fictifs).\n"
           "const REPONSES = " + json.dumps(reponses, ensure_ascii=False).replace("</", "<\\/") + ";\n"
           "window.fetch = async (url) => { const u = String(url); const r = REPONSES[u];\n"
           "  return { ok: !!r || u === '/connexion', status: r ? 200 : 404, json: async () => r || { erreur: 'absent de l\\'aperçu : ' + u } }; };\n")
html = (page.replace('<link rel="stylesheet" href="/app.css">', "<style>\n" + (SRC / "bin/page/app.css").read_text() + "</style>")
            .replace('<script src="/app.js" defer></script>', "")
            .replace("<body>", "<body>\n" + BANDEAU)
            .replace("</body>", "<script>\n" + serveur + "</script>\n<script>\n" + (SRC / "bin/page/app.js").read_text() + "</script>\n</body>"))
SORTIE.parent.mkdir(parents=True, exist_ok=True); SORTIE.write_text(html)
print(f"aperçu écrit : {SORTIE.relative_to(SRC)} ({len(html) // 1024} Ko, {len(reponses)} réponses)")
