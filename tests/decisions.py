#!/usr/bin/env python3
"""Tests des onglets « Décisions » et « Checklists », et du rangement des onglets — sans modèle, avec un FAUX Herdr et un
FAUX serveur d'API Herdr (jamais le vrai). Décisions : validation pour le propriétaire / pour un valideur, agent bloqué,
question laissée par un agent (et pas quand un humain a répondu, ni quand le « ? » est dans du code, ni au-delà de 48 h),
document à lire. Checklists : avancement, seules les cases restantes, sous leur section ; dossier vide dit. Rangement :
tab.move envoyé au faux serveur pour remettre Synthèse et Sources après Tableau ; jamais au vrai serveur.
Usage : python3 tests/decisions.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import datetime, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent)); import _produit

SRC = Path(__file__).resolve().parent.parent
ko = 0


def dire(ok, texte):
    global ko
    ko += not ok; print(("ok    " if ok else "ÉCHEC ") + texte)


net = lambda t: re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", t)
larg = lambda s: sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def conversation(f, messages):
    """Écrit une conversation Claude (une entrée JSON par ligne) : [(type, texte, il y a combien d'heures)]."""
    lignes = []
    for type_, texte, heures in messages:
        q = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=heures)).isoformat().replace("+00:00", "Z")
        c = texte if type_ == "user" else [{"type": "text", "text": texte}]
        lignes.append(json.dumps({"type": type_, "timestamp": q, "message": {"role": type_, "content": c}}))
    lignes.insert(0, json.dumps({"type": "user", "entrypoint": "cli", "message": {"content": [{"type": "tool_result", "content": "x"}]}}, separators=(",", ":")))
    f.write_text("\n".join(lignes) + "\n")


with tempfile.TemporaryDirectory() as t:
    t = Path(t); m = t / "maison"; i = m / "berger"; m.mkdir()
    _produit.copier(SRC, i, ("bin", "courtier", "commun"))
    (m / "coffre.json").write_text("{}")
    ck = m / "listes"; ck.mkdir()
    (i / "config.toml").write_text(f'proprietaire = "Proprio"\nmasques = []\ncoffre = "{m}/coffre.json"\n[checklists]\ndossier = "{ck}"\n')
    statut = t / "statut"; statut.write_text("idle")
    (t / "herdr").write_text('#!/bin/sh\nif [ "$1 $2" = "pane get" ]; then echo "{\\"result\\": {\\"pane\\": {\\"agent_status\\": \\"$(cat ' + str(statut) + ')\\"}}}"; '
                             'else echo \'{"result": {}}\'; fi\n'); os.chmod(t / "herdr", 0o755)
    env = {**os.environ, "HOME": str(m), "BERGER_DIR": str(i), "BERGER_HERDR": str(t / "herdr")}
    env.pop("BERGER_HERDR_SOCKET", None)
    b = lambda *a: subprocess.run([sys.executable, str(i / "bin/berger"), *a], env=env, capture_output=True, text=True, timeout=60)
    for a, n in (("vigie", "Vigie"), ("scribe", "Scribe")): b("nouveau", a, n)
    for a in ("vigie", "scribe"):                                         # moteur claude, panneau d'agent connu de Herdr
        f = i / "agents" / a / "agent.conf"; f.write_text(f.read_text().replace("moteur = codex", "moteur = claude").replace("panneaux = codex", "panneaux = claude"))
    (i / "agents/scribe/.herdr.json").write_text(json.dumps({"agents": {"claude": "w1:p1"}}))
    conv = lambda a: m / ".claude/projects" / re.sub(r"[^A-Za-z0-9]", "-", str(i / "agents" / a))
    for a in ("vigie", "scribe"): conv(a).mkdir(parents=True); (i / "agents" / a / ".conversation-claude").write_text("c1")

    v = i / "courtier/validations"; v.mkdir(parents=True, exist_ok=True)
    (v / "3.json").write_text(json.dumps({"n": 3, "agent": "vigie", "apercu": "couper le compte de test", "demande": "2026-10-07T09:00:00"}))
    (v / "4.json").write_text(json.dumps({"n": 4, "agent": "scribe", "valideur": "vigie", "apercu": "fusionner la branche", "demande": "2026-10-07T09:05:00"}))
    (i / "a-lire").mkdir(exist_ok=True); (i / "a-lire/rapport.md").write_text("# Rapport du matin\n")

    vue = (f"import runpy,sys,json;sys.argv=['b'];g=runpy.run_path({str(i / 'bin/berger')!r},run_name='x');"
           "print(json.dumps({'dec':g['VUES']['decisions'].vue_decisions(%d,60),'ck':g['VUES']['checklists'].vue_checklists(%d,60),'q':[str(g['question_en_attente'](a)) for a in ('vigie','scribe')],"
           "'onglets':[l for l,_ in g['ONGLETS_BERGER']],'icones':[g['ICONES_ONGLETS'].get(k) for k in ('Décisions','Checklists')],"
           "'dep':g['deplacements'](%s),'sock':g['socket_herdr']()}))")
    VM = ["Accueil", "Tableau", "Synthèse", "À lire", "Courtier", "Échanges", "Catalogue", "Tokens", "Sources"]
    lance = lambda w, noms=VM, **e: json.loads(subprocess.run([sys.executable, "-c", vue % (w, w, json.dumps(noms))], env={**env, **e},
                                                              capture_output=True, text=True, timeout=60).stdout or "{}")

    # ── Décisions
    conversation(conv("vigie") / "c1.jsonl", [("user", "vérifie la règle 301", 3), ("assistant", "C'est fait. Je bascule Vigie maintenant ?", 2)])
    conversation(conv("scribe") / "c1.jsonl", [("assistant", "Tu veux le rapport ?", 3), ("user", "oui", 2)])
    x = lance(160); dec = "\n".join(net(l) for l in x["dec"]); toi = dec.split("T'ATTEND")[1].split("ATTEND UN AGENT")[0]; autre = dec.split("ATTEND UN AGENT")[1]
    dire("validation n° 3" in toi and "berger valider 3" in toi, "validation sans valideur : dans T'ATTEND, avec la commande")
    dire("validation n° 4" in autre and "attend Vigie" in autre and "validation n° 4" not in toi, "validation confiée à un valideur : dans ATTEND UN AGENT")
    dire("Je bascule Vigie maintenant ?" in toi, "dernier message de l'agent = une question : dans T'ATTEND, citée")
    dire("Tu veux le rapport" not in dec, "question à laquelle un humain a répondu : absente")
    dire("1 document à lire" in toi and "Rapport du matin" in toi, "document non lu : dans T'ATTEND")
    dire(all(larg(net(l)) <= 60 for l in lance(60)["dec"]), "Décisions : largeur jamais dépassée (60 colonnes)")
    statut.write_text("blocked")
    dire("attend une réponse dans son terminal" in "\n".join(net(l) for l in lance(160)["dec"]), "agent arrêté sur une permission (Herdr « blocked ») : dans T'ATTEND")
    statut.write_text("idle")
    conversation(conv("vigie") / "c1.jsonl", [("assistant", "Lance `ls ?` puis lis https://exemple.org/a?b=1 — c'est tout.", 1)])
    conversation(conv("scribe") / "c1.jsonl", [("assistant", "On y va ?", 49)])
    dire(lance(160)["q"] == ["None", "None"], f"« ? » dans du code ou une adresse, ou question de plus de 48 h : ignorés (obtenu {lance(160)['q']})")
    conversation(conv("vigie") / "c1.jsonl", [("assistant", "Je bascule ?", 1)])
    (i / "agents/vigie/.conversation-claude").unlink()                   # pas d'id noté : la dernière conversation interactive
    dire(lance(160)["q"][0].startswith("('Je bascule ?'"), "sans id noté : la dernière conversation interactive de l'agent est lue")

    # ── Checklists
    x = lance(160); ckv = "\n".join(net(l) for l in x["ck"])
    dire("aucune liste" in ckv, "dossier de checklists vide : le panneau le dit")
    (ck / "feuille.md").write_text("# Feuille de route\n## Étape 4\n- [x] Vigie basculée\n- [ ] Intendant\n## Étape 5\n- [x] VM prête\n- [x] testée\n## Étape 6\n- [ ] mesures\n")
    x = lance(160); ckv = "\n".join(net(l) for l in x["ck"])
    dire("Feuille de route" in ckv and "3/5" in ckv, "avancement : titre et cases faites / total")
    dire("☐ Intendant" in ckv and "☐ mesures" in ckv and "Vigie basculée" not in ckv, "seules les cases restantes sont listées")
    dire("Étape 4" in ckv and "Étape 6" in ckv and "Étape 5" not in ckv, "une section n'apparaît que s'il lui reste une case")
    (ck / "feuille.md").write_text("# Fini\n- [x] a\n")
    dire("✔ terminé" in "\n".join(net(l) for l in lance(160)["ck"]), "liste entièrement cochée : « terminé »")
    dire(all(larg(net(l)) <= 60 for l in lance(60)["ck"]), "Checklists : largeur jamais dépassée (60 colonnes)")

    # ── onglets et rangement
    dire(x["onglets"][:7] == ["Livrables", "Documents", "Tableau", "Synthèse", "Sources", "Décisions", "Checklists"], f"ordre des onglets : Livrables et Documents en tête, Synthèse et Sources juste après Tableau (obtenu {x['onglets'][:7]})")
    dire(x["icones"] == ["🔔", "✅"], f"icônes Décisions et Checklists (obtenu {x['icones']})")
    dire(x["dep"] == [["Sources", 3]], f"espace existant (Sources en fin) : un seul tab.move, Sources en 4e place (obtenu {x['dep']})")
    dire(lance(160, ["Accueil", "Tableau", "Synthèse", "Sources", "Décisions", "Checklists", "À lire"])["dep"] == [], "espace déjà rangé : aucun déplacement")
    dire(x["sock"] is None, "Herdr de remplacement sans BERGER_HERDR_SOCKET : aucune socket (jamais le vrai serveur)")

    # faux serveur d'API Herdr : reçoit les tab.move de refaire-espace
    recu = []; chemin = str(t / "api.sock"); srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(chemin); srv.listen(5)

    def servir():
        while True:
            try: c, _ = srv.accept()
            except OSError: return
            with c:
                d = b""
                while not d.endswith(b"\n"): d += c.recv(4096)
                q = json.loads(d); recu.append(q); c.sendall((json.dumps({"id": q["id"], "result": {"type": "tab_list", "tabs": []}}) + "\n").encode())
    threading.Thread(target=servir, daemon=True).start()
    onglets = ["🏠 Accueil", "📋 Tableau", "🚦 Synthèse", "📖 À lire", "🔐 Courtier", "💬 Échanges", "📚 Catalogue", "🪙 Tokens", "🔎 Sources", "🔔 Décisions", "✅ Checklists", "📐 Livrables", "🗂 Documents"]   # tous présents (rien à créer), hors d'ordre
    (t / "herdr").write_text("#!/usr/bin/env python3\nimport json,sys\na=sys.argv[1:]\nr={}\n"
                             "if a[:2]==['workspace','list']: r={'workspaces':[{'workspace_id':'w1','label':'Berger'}]}\n"
                             f"elif a[:2]==['tab','list']: r={{'tabs':[{{'tab_id':'w1:t%d'%(n+1),'label':l}} for n,l in enumerate({onglets!r})]}}\n"
                             "elif a[:2]==['pane','list']: r={'panes':[{'pane_id':'w1:p1','tab_id':'w1:t1'}]}\n"
                             "print(json.dumps({'result':r}))\n")
    r = subprocess.run([sys.executable, str(i / "bin/berger"), "refaire-espace", "berger"], env={**env, "BERGER_HERDR_SOCKET": chemin},
                       capture_output=True, text=True, timeout=60)
    srv.close()
    deplaces = [(q["method"], q["params"]["insert_index"]) for q in recu]
    dire(r.returncode == 0 and deplaces and all(mq == "tab.move" for mq, _ in deplaces) and "remis en ordre" in r.stdout,
         f"refaire-espace berger : onglets remis en ordre par tab.move sur l'API Herdr (reçu {deplaces}, code {r.returncode} {r.stderr.strip()[-160:]})")

print(f"\n{'tout passe' if not ko else f'{ko} échec(s)'}")
sys.exit(1 if ko else 0)
