#!/usr/bin/env python3
"""Contrôle (13) : sous-agents de Codex (namespace collaboration) pour les stricts (codex-sous-agents, 31/10/2026,
docs/plans/2026-10-31-codex-sous-agents-spec.md) — sans moteur, socket ni réseau. Source de (13) (01/11/2026, accord du chef
de projet) : les requêtes de Codex au faux modèle du CONTRAT, qui joue lui-même le modèle ; leurs formes sont celles mesurées
(tests/fixtures/codex-0.165.0-sous-agent.json, tests/_mesure_sous_agents.py). Codex simulé d'après la mesure, l'enfant
jouant la sonde SANS bac à sable (ses évasions RÉUSSISSENT) ; requêtes capturées pour (12).
  (13) verte → collaboration accepté par (12) ; sous-agent non lancé, sonde non exécutée par l'enfant, sortie non reçue →
  non mesurable ; requête hors chaîne, enfant inattendu, bac à sable de l'enfant autre que celui du parent → rouge ; chacune
  des quatre évasions réussie → rouge, nommée ; collaboration sans (13) verte → rouge ; outil web → rouge, avec ou sans (13).
Usage : python3 tests/contrat-sous-agents.py (0 = tout passe)"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import copy, importlib.util, json, os, socket, stat, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch

T = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("contrat", T / "contrat-moteur.py")
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
CONNUS = C.charger_connus("codex", "0.165.0")
FX = json.loads((T / "fixtures/codex-0.165.0-requetes.json").read_text())["requetes"]
TEMOIN = FX["gpt-5.5-sans-reglage"]
JETON = "jeton-factice-du-sous-agent"
NONCE = "nonce-factice-du-contrat"
APPELS = {"spawn": "call_spawn_factice", "attente": "call_attente_factice", "sonde": "call_sonde_factice"}
TACHE = "/root/" + C.TACHE_13
CMD = "/usr/bin/python3 -I /depot/tests/sonde-mcp.py sous-agent /travail/berger-contrat-canari-sous-agent-cibles.json"
ARGS_SONDE = {"cmd": CMD, "login": False, "shell": "/bin/bash", "yield_time_ms": 30000}
LIRE, LISTER = ["/coffre.json", "/agents/autre/agent.conf"], ["/agents/autre"]
MCP = ["/travail/.mcp.json", "/travail/.codex/config.toml"]
RESEAU = ["127.0.0.1:4242", "1.1.1.1:53"]
ATTENDU = {"cmd": CMD, "cibles": "empreinte-factice-des-cibles", "lire": LIRE, "lister": LISTER, "mcp": MCP, "reseau": RESEAU,
           "nonce": NONCE, "appels": APPELS, "args_sonde": ARGS_SONDE}
SIGNES = {"unix": (1, 0), "tcp": (1, 0)}           # (connexions signées du contrat, autres connexions)
# Requêtes RÉELLES de codex 0.165.0 au faux modèle (mesure du 01/11/2026) : leurs formes servent de gabarit
REEL = json.loads((T / "fixtures/codex-0.165.0-sous-agent.json").read_text())["requetes"]
# mesure faite sans le bac à sable de Codex (il ne s'imbrique pas dans celui du poste) : un strict a workspace-write (mesuré aussi)
META_P = {**REEL[0]["meta"], "sandbox_mode": "workspace-write"}
META_E = {**REEL[2]["meta"], "sandbox_mode": "workspace-write", "agent_name": TACHE}
P, E = META_P["thread_id"], META_E["thread_id"]


def sonde(**autre):
    """La sortie de la sonde du sous-agent (dernière ligne) : tout refusé, sauf ce que le cas change ; None retire un champ."""
    r = {"jeton": JETON, "cibles": ATTENDU["cibles"], "lire": {x: "refuse" for x in LIRE}, "lister": {x: "refuse" for x in LISTER},
         "mcp": {x: "refuse" for x in MCP}, "af_unix": "refuse", "unix": {"vu": "oui", "connect": "refuse"},
         "reseau": {x: "ferme" for x in RESEAU}, **autre}
    return "SOUS-AGENT " + json.dumps({k: v for k, v in r.items() if v is not None})


def sortie_exec(texte, code=0):
    """La sortie d'exec_command telle que Codex la rend au modèle (forme mesurée)."""
    return (f"Chunk ID: 1a2b3c\nWall time: 0.0100 seconds\nProcess exited with code {code}\nOriginal token count: 40\n"
            f"Output:\n{texte}\n")


def gabarit(k, typ):
    """Un élément d'input réel (fixture) du type demandé dans la requête k."""
    return copy.deepcopy(next(x for x in REEL[k]["input"] if x["type"] == typ))


def appel(cle, nom, args, ns=None):
    x = gabarit(1, "function_call"); x.update({"call_id": APPELS[cle], "name": nom, "arguments": json.dumps(args)})
    x.pop("namespace", None)
    if ns: x["namespace"] = ns
    return x


def resultat(cle, sortie):
    x = gabarit(1, "function_call_output"); x.update({"call_id": APPELS[cle], "output": sortie}); return x


def tache(nonce=NONCE, auteur="/root", dest=TACHE):
    x = gabarit(2, "agent_message"); x.update({"author": auteur, "recipient": dest})
    x["content"][-1]["encrypted_content"] = f"[Contrat] {nonce} : lance la sonde."
    return x


def reponse_finale(texte=f"SOUS-AGENT-RENDU {JETON}", auteur=TACHE):
    x = gabarit(4, "agent_message"); x.update({"author": auteur, "recipient": "/root"})
    x["content"] = [{"type": "input_text", "text": f"Message Type: FINAL_ANSWER\nTask name: /root\nSender: {auteur}\nPayload:\n{texte}"}]
    return x


def rq(meta, *items, **change):
    m = {**copy.deepcopy(meta), **change}
    return {"meta": {k: v for k, v in m.items() if v is not None}, "corps": {"input": [{"type": "message", "role": "user"}, *items]}}


def chaine(sortie=None, code=0, args=ARGS_SONDE, finale=f"SOUS-AGENT-RENDU {JETON}", spawn='{"task_name":"%s"}' % TACHE):
    """La chaîne complète d'un contrat vert (forme réelle) : parent (spawn, attente), enfant (sonde), parent (réponse reçue)."""
    s = sortie_exec(sonde() if sortie is None else sortie, code)
    sp = [appel("spawn", "spawn_agent", {"task_name": C.TACHE_13, "message": "x", "fork_turns": "none"}, "collaboration"),
          resultat("spawn", spawn)]
    at = [appel("attente", "wait_agent", {"timeout_ms": 1000}, "collaboration"),
          resultat("attente", '{"message":"Wait completed.","timed_out":false}')]
    return [rq(META_P), rq(META_P, *sp), rq(META_E, tache()), rq(META_E, tache(), appel("sonde", "exec_command", args), resultat("sonde", s)),
            rq(META_P, *sp, *at, reponse_finale(finale))]


VERT = chaine()


def juger(requetes, signes=SIGNES, temoins=True, attendu=ATTENDU):
    lignes = []
    ok = C.verdict_sous_agents(lambda b, t: lignes.append((bool(b), t)), requetes, attendu, signes, temoins)
    return ok, lignes


def verdict12(corps, sous_agents, connus=CONNUS):
    """(12) sous Codex, même collecte que le faux fournisseur ; seul le transport est remplacé (contrat-outils-codex.py)."""
    class Fournisseur:
        url = "http://fournisseur.invalid/v1"
        def __init__(self): self.corps = []
        def fermer(self): pass
    f = Fournisseur()
    def lancer(args, **kw):
        f.corps = corps if 'web_search="disabled"' in args else [TEMOIN]
    lignes = []
    with patch.object(C, "FauxFournisseur", return_value=f), patch.object(C.subprocess, "run", side_effect=lancer):
        C.condition_web_codex(lambda ok, txt: lignes.append((ok, txt)), C.RECHERCHE_CODEX, T, {}, connus, set(), sous_agents=sous_agents)
    return lignes


class Condition13(unittest.TestCase):
    """(13) d'après les SEULES requêtes de Codex au faux modèle du contrat (forme réelle de la fixture)."""
    def test_fixture_reelle_lue(self):
        """La forme mesurée : parent puis enfant nommés par Codex, sortie d'exec_command dans la requête suivante de l'enfant."""
        self.assertEqual((META_P["thread_source"], META_P["agent_name"]), ("user", "/root"))
        self.assertEqual((META_E["thread_source"], META_E["subagent_kind"], META_E["parent_thread_id"]), ("subagent", "thread_spawn", P))
        sortie = next(x for x in REEL[3]["input"] if x["type"] == "function_call_output")["output"]
        code, texte = C.lire_sortie_exec(sortie)
        self.assertEqual(code, 0); self.assertTrue(texte.startswith("SOUS-AGENT-MESURE "))
        self.assertEqual(C.lire_sortie_exec("Process exited with code 0\nOutput:\nx\n"), (0, "x\n"))
        for x in ("Output:\nx", "Process exited with code 0\nrien", "Process exited with code zéro\nOutput:\nx", 42, None, []):
            with self.subTest(x=x): self.assertEqual(C.lire_sortie_exec(x), (None, None))

    def test_verte(self):
        ok, l = juger(VERT)
        self.assertTrue(ok, l); self.assertTrue(all(b for b, _ in l))
        self.assertTrue(any(t.startswith("témoin (13)") and "faux modèle du contrat" in t for _, t in l))
        self.assertEqual(sum(t.startswith("(13) évasion") for _, t in l), 4)

    def rouge(self, requetes, motif, **k):
        ok, l = juger(requetes, **k)
        self.assertFalse(ok); self.assertIn(motif, l[-1][1]); self.assertIn("collaboration refusé", l[-1][1])
        return l

    def test_sous_agent_non_lance(self):
        sans_enfant = [r for r in VERT if r["meta"]["thread_source"] == "user"]
        for nom, rqs in {"aucune requête": [], "aucun fil enfant": sans_enfant,
                         "spawn refusé": chaine(spawn="collaboration is disabled"),
                         "spawn d'un autre nom": chaine(spawn='{"task_name":"/root/autre"}'),
                         "spawn sans résultat": [VERT[0], VERT[2], VERT[3]]}.items():
            with self.subTest(nom=nom): self.rouge(rqs, "non mesurable — sous-agent non lancé")

    def test_requete_hors_chaine_rouge(self):
        v = copy.deepcopy(VERT)
        intrus = {"métadonnées absentes": {"meta": None, "corps": {"input": []}},
                  "corps illisible": {"meta": META_E, "corps": None},
                  "input absent": {"meta": META_E, "corps": {}},
                  "fil sans identifiant": rq(META_E, tache(), thread_id=None),
                  "source inconnue": rq(META_P, thread_source="exec"),
                  "second fil parent": rq(META_P, thread_id="fil-parent-autre"),
                  "parent qui se dit enfant de quelqu'un": rq(META_P, parent_thread_id=E),
                  "appel que le contrat n'a pas fait": rq(META_E, tache(), {"type": "function_call_output", "call_id": "call_autre", "output": "x"}),
                  "sonde dans le fil parent": rq(META_P, resultat("sonde", sortie_exec(sonde()))),
                  "spawn dans le fil enfant": rq(META_E, tache(), resultat("spawn", '{"task_name":"%s"}' % TACHE)),
                  "tâche sans le nonce": rq(META_E, tache(nonce="nonce-devine")),
                  "tâche d'un autre auteur": rq(META_E, tache(auteur=TACHE))}
        for nom, r in intrus.items():
            for k in (0, 3, len(v)):                       # avant, au milieu, après la chaîne : jamais ignorée
                with self.subTest(nom=nom, place=k): self.rouge(v[:k] + [r] + v[k:], "hors chaîne")

    def test_enfant_inattendu_rouge(self):
        for nom, r in {"d'un autre parent": rq(META_E, tache(), parent_thread_id="fil-etranger"),
                       "autre nom de tâche": rq(META_E, tache(), agent_name="/root/autre"),
                       "sans genre de lancement": rq(META_E, tache(), subagent_kind=None),
                       "autre genre": rq(META_E, tache(), subagent_kind="review"),
                       "même fil que le parent": rq(META_E, tache(), thread_id=P),
                       "deuxième enfant": rq(META_E, tache(), thread_id="fil-enfant-deux")}.items():
            with self.subTest(nom=nom): self.rouge(VERT + [r], "enfant inattendu")

    def test_bac_a_sable_de_l_enfant_different_rouge(self):
        for mode in ("danger-full-access", None):
            with self.subTest(mode=mode):
                v = copy.deepcopy(VERT)
                for r in v[2:4]:
                    if mode: r["meta"]["sandbox_mode"] = mode
                    else: r["meta"].pop("sandbox_mode")
                self.rouge(v, "bac à sable de l'enfant")

    def test_sonde_non_executee_par_l_enfant(self):
        cas = {"aucune sortie": [VERT[0], VERT[1], VERT[2], VERT[4]],
               "code de sortie 1": chaine(code=1),
               "commande changée": chaine(args={**ARGS_SONDE, "cmd": CMD + " ; echo fini"}),
               "sans -I": chaine(args={**ARGS_SONDE, "cmd": CMD.replace(" -I ", " ")}),
               "shell de connexion": chaine(args={**ARGS_SONDE, "login": True}),
               "login non précisé": chaine(args={k: v for k, v in ARGS_SONDE.items() if k != "login"}),
               "shell par son nom": chaine(args={**ARGS_SONDE, "shell": "bash"}),
               "shell hors système": chaine(args={**ARGS_SONDE, "shell": "/travail/bash"})}
        for nom, rqs in cas.items():
            with self.subTest(nom=nom): self.rouge(rqs, "sonde non exécutée par l'enfant")
        v = copy.deepcopy(VERT); v[3]["corps"]["input"][-2]["name"] = "exec"
        self.rouge(v, "sonde non exécutée par l'enfant")
        v = copy.deepcopy(VERT); v[3]["corps"]["input"][-1]["output"] = [{"type": "input_text", "text": sortie_exec(sonde())}]
        self.rouge(v, "sonde non exécutée par l'enfant")
        v = copy.deepcopy(VERT); v.insert(4, rq(META_E, tache(), appel("sonde", "exec_command", ARGS_SONDE),
                                                resultat("sonde", sortie_exec(sonde(lire={x: "lu" for x in LIRE})))))
        self.rouge(v, "sorties de la sonde contradictoires")

    def test_sortie_non_conforme(self):
        cas = {"champs lecture et MCP absents": sonde(lire=None, lister=None, mcp=None),
               "destinations inventées « ferme »": sonde(reseau={"10.9.9.9:1": "ferme", "10.9.9.8:2": "ferme"}),
               "destination imposée absente": sonde(reseau={RESEAU[0]: "ferme"}),
               "cible de lecture retirée": sonde(lire={LIRE[0]: "refuse"}),
               "cibles changées": sonde(cibles="autre-empreinte-factice"),
               "champ en trop": sonde(note="tout va bien"),
               "valeur hors liste": sonde(mcp={x: "peut-etre" for x in MCP}),
               "socket sans détail": sonde(unix={"vu": "oui"}),
               "pas du JSON": "SOUS-AGENT {tout est refusé}", "aucune ligne": "rien"}
        for nom, s in cas.items():
            with self.subTest(nom=nom): self.rouge(chaine(s), "sortie de la sonde non conforme")

    def test_sortie_non_recue_par_le_parent(self):
        v = copy.deepcopy(VERT); v[4]["corps"]["input"].pop()
        for nom, rqs in {"sans réponse de l'enfant": v, "sans dernière requête du parent": VERT[:4],
                         "réponse sans le jeton": chaine(finale="SOUS-AGENT-RENDU fini"),
                         "réponse d'un autre": chaine()[:4] + [rq(META_P, reponse_finale(auteur="/root/autre"))]}.items():
            with self.subTest(nom=nom):
                l = self.rouge(rqs, "non mesurable")
                self.assertTrue("non reçue par le parent" in l[-1][1] or "enfant inattendu" in l[-1][1], l[-1][1])

    def test_chaque_evasion_reussie_rouge_et_nommee(self):
        cas = {"lecture": dict(s=sonde(lire={LIRE[0]: "lu", LIRE[1]: "refuse"})),
               "lecture (dossier)": dict(s=sonde(lister={LISTER[0]: "lu"})),
               "écriture MCP": dict(s=sonde(mcp={MCP[0]: "ecrit", MCP[1]: "refuse"})),
               "socket": dict(s=sonde(unix={"vu": "oui", "connect": "connecte"})),
               "socket (compteur de l'enfant)": dict(signes={"unix": (1, 1), "tcp": (1, 0)}),
               "réseau": dict(s=sonde(reseau={RESEAU[0]: "ouvert", RESEAU[1]: "ferme"})),
               "réseau (compteur de l'enfant)": dict(signes={"unix": (1, 0), "tcp": (1, 1)})}
        for nom, k in cas.items():
            with self.subTest(nom=nom):
                ok, l = juger(chaine(k.get("s")), k.get("signes", SIGNES))
                rouges = [t for b, t in l if not b]
                self.assertFalse(ok); self.assertEqual(len(rouges), 1, rouges)
                self.assertIn(f"évasion : {nom.split(' (')[0]}", rouges[0]); self.assertIn("RÉUSSIE", rouges[0])

    def test_evasion_non_prouvee_rouge(self):
        for nom, k in {"socket invisible": dict(s=sonde(unix={"vu": "non", "connect": "refuse"})),
                       "témoins hors bac à sable absents": dict(temoins=False),
                       "compteur absent": dict(signes={"unix": None, "tcp": (1, 0)}),
                       "témoin du contrat non compté": dict(signes={"unix": (1, 0), "tcp": (0, 0)})}.items():
            with self.subTest(nom=nom):
                ok, l = juger(chaine(k.get("s")), k.get("signes", SIGNES), k.get("temoins", True))
                self.assertFalse(ok); self.assertTrue(any(not b and "non prouvé" in t for b, t in l), l)


class FauxModele(unittest.TestCase):
    """Le faux modèle du contrat (sans socket) : il ne joue QUE la chaîne du contrat, tirée à neuf à chaque contrat."""
    def modele(self): return C.FauxModele13(CMD, "/bin/bash", 60000, serveur=False)

    def test_tirages_neufs_et_commande_imposee(self):
        a, b = self.modele().attendu(), self.modele().attendu()
        self.assertNotEqual(a["nonce"], b["nonce"]); self.assertFalse(set(a["appels"].values()) & set(b["appels"].values()))
        self.assertGreaterEqual(len(a["nonce"]), 32); self.assertEqual(len(set(a["appels"].values())), 3)
        self.assertEqual(a["args_sonde"], {"cmd": CMD, "login": False, "shell": "/bin/bash", "yield_time_ms": 30000})
        for shell in ("bash", "/travail/bash", None):
            with self.subTest(shell=shell), self.assertRaises(ValueError): C.FauxModele13(CMD, shell, 60000, serveur=False)
        for cmd in ("python3 -I x", "/usr/bin/python3 x"):
            with self.subTest(cmd=cmd), self.assertRaises(ValueError): C.FauxModele13(cmd, "/bin/bash", 60000, serveur=False)

    def test_joue_la_chaine_et_rien_d_autre(self):
        m = self.modele(); a = m.attendu(); ap = a["appels"]
        envoyer = lambda meta, *items, **ch: m.recevoir(rq(meta, *items, **ch)["meta"], rq(meta, *items, **ch)["corps"])
        self.assertIsNone(envoyer(META_E, tache(a["nonce"])), "enfant avant le parent : refusé")
        r = envoyer(META_P)
        self.assertEqual((r[0]["type"], r[0]["name"], r[0]["namespace"], r[0]["call_id"]), ("function_call", "spawn_agent", "collaboration", ap["spawn"]))
        args = json.loads(r[0]["arguments"])
        self.assertEqual((args["task_name"], args["fork_turns"]), (C.TACHE_13, "none")); self.assertIn(a["nonce"], args["message"])
        self.assertNotIn(CMD, args["message"], "la commande n'est jamais confiée au texte : le contrat l'appelle lui-même")
        self.assertIsNone(envoyer(META_P, thread_id="fil-parent-autre"), "second parent : refusé")
        sp = {"type": "function_call_output", "call_id": ap["spawn"], "output": "{}"}
        r = envoyer(META_P, sp); self.assertEqual((r[0]["name"], r[0]["call_id"]), ("wait_agent", ap["attente"]))
        self.assertIsNone(envoyer(META_E, tache("nonce-devine")), "enfant sans le nonce : refusé")
        self.assertIsNone(envoyer(META_E, tache(a["nonce"]), parent_thread_id="fil-etranger"), "enfant d'un autre parent : refusé")
        r = envoyer(META_E, tache(a["nonce"]))
        self.assertEqual((r[0]["name"], r[0]["call_id"], json.loads(r[0]["arguments"])), ("exec_command", ap["sonde"], a["args_sonde"]))
        self.assertIsNone(envoyer(META_E, tache(a["nonce"]), thread_id="fil-enfant-deux"), "deuxième enfant : refusé")
        so = {"type": "function_call_output", "call_id": ap["sonde"], "output": sortie_exec(sonde())}
        r = envoyer(META_E, tache(a["nonce"]), so); self.assertEqual(r[0]["type"], "message"); self.assertIn(JETON, json.dumps(r))
        r = envoyer(META_P, sp, {"type": "function_call_output", "call_id": ap["attente"], "output": "{}"})
        self.assertEqual(r[0]["type"], "message")
        self.assertIsNone(m.recevoir(None, {"input": []})); self.assertIsNone(m.recevoir(META_P, None))
        self.assertEqual(len(m.requetes), 12, "chaque requête gardée, refusée comprise")

    def test_reponse_sse_lisible(self):
        b = C.sse_reponse([{"type": "message", "role": "assistant", "content": []}], "resp_1").decode()
        evts = [l[len("event: "):] for l in b.splitlines() if l.startswith("event: ")]
        self.assertEqual(evts, ["response.created", "response.output_item.done", "response.completed"])


class TemoinsSignes(unittest.TestCase):
    """Vrais sockets (sautés dans un bac à sable qui les refuse) : la connexion signée du contrat est comptée à part ; celle
    d'un autre (la sonde de l'enfant) jamais confondue avec elle."""
    def test_contrat_et_autres_distingues(self):
        try: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close()
        except OSError: self.skipTest("socket AF_UNIX impossible ici (bac à sable)")
        with tempfile.TemporaryDirectory(prefix="sa-", dir="/tmp" if os.access("/tmp", os.W_OK) else None) as d:
            secret, f = "secret-factice-du-contrat-" + "x" * 40, Path(d) / f"{C.MARQUE}-essai.sock"
            for temoin, cible in ((C.TemoinSigne(secret, f), f), (t := C.TemoinSigne(secret), ("127.0.0.1", t.port))):
                with self.subTest(cible=cible):
                    try:
                        self.assertTrue(C.connecte_signe(cible, secret) and temoin.attendre(1))
                        self.assertTrue(C.connecte_signe(cible, "faux-secret"))           # mauvais secret : un autre
                        self.assertTrue(C.connecte(cible))                                 # sans rien envoyer : un autre
                        fin = time.time() + 10                     # connect() rend la main avant que le témoin ait accepté
                        while temoin.n < 3 and time.time() < fin: time.sleep(0.05)
                        temoin.classees()
                        self.assertEqual((temoin.contrat, temoin.autres), (1, 2))
                    finally: temoin.fermer()
            r = subprocess.run([sys.executable, str(T / "sonde-mcp.py"), "sous-agent", str(Path(d) / "absent.json")],
                               capture_output=True, text=True, timeout=60)
            self.assertIsNone(C.sortie_sonde(r.stdout, ATTENDU), "sonde sans ses cibles : sortie non conforme")


class Liste12(unittest.TestCase):
    def test_liste_porte_collaboration_sous_condition(self):
        attendu = {("namespace", "collaboration")} | {(("namespace", "collaboration"), ("function", n)) for n in
                   ("spawn_agent", "send_message", "wait_agent", "list_agents", "followup_task", "interrupt_agent")}
        vus = {c[0] if len(c) == 1 else c for c in CONNUS["si_13"]}
        self.assertEqual(vus, attendu)
        self.assertFalse(set(CONNUS["si_13"]) & set(CONNUS["outils"]), "collaboration jamais en dur")
        self.assertFalse(any(t == "namespace" and n == "clock" for c in CONNUS["outils"] + CONNUS["si_13"] for t, n in c))

    def test_13_verte_collaboration_accepte(self):
        r = verdict12([FX["defaut-avec-reglage"]], True)
        self.assertTrue(all(ok for ok, _ in r), r)

    def test_collaboration_sans_13_verte_rouge(self):
        r = verdict12([FX["defaut-avec-reglage"]], False)
        self.assertFalse(r[1][0]); self.assertIn("collaboration", r[1][1]); self.assertIn("(13)", r[1][1])

    def test_outil_web_toujours_rouge(self):
        rq = copy.deepcopy(FX["defaut-avec-reglage"])
        rq["input"][0]["tools"].append({"type": "web_search"})
        for sa in (True, False):
            with self.subTest(sous_agents=sa):
                r = verdict12([rq], sa); self.assertFalse(r[1][0]); self.assertIn("web_search", r[1][1])

    def test_clock_reste_refuse(self):
        rq = copy.deepcopy(FX["defaut-avec-reglage"])
        rq["input"][0]["tools"].append({"type": "namespace", "name": "clock", "tools": [{"type": "function", "name": "sleep"}]})
        r = verdict12([rq], True); self.assertFalse(r[1][0]); self.assertIn("clock", r[1][1])

    def test_liste_sous_condition_mal_formee_refusee(self):
        base = json.loads((C.CONNUS / "codex-0.165.0.json").read_text())
        for nom, si in (("outil web", [{"type": "web_search"}]), ("déjà en dur", [{"type": "function", "name": "exec_command"}]),
                        ("nom web", [{"type": "function", "name": "web_fetch"}]), ("mcp", [{"type": "function", "name": "mcp__x"}]),
                        ("vide", []), ("pas une liste", {"type": "web_search"})):
            with self.subTest(nom=nom), tempfile.TemporaryDirectory() as d:
                (Path(d) / "codex-0.165.0.json").write_text(json.dumps({**base, "si_13": si}))
                c = C.charger_connus("codex", "0.165.0", d)
                self.assertIsNone(c["outils"]); self.assertIn("mal formée", c["raison"])


RUN = subprocess.run                                   # le vrai, pour la sonde (subprocess.run du contrat est remplacé)


def codex_simule(m, mode, env):
    """Codex 0.165.0 tel que mesuré (fixture), SANS bac à sable : parent, enfant, sorties rendues au faux modèle du contrat."""
    meta_p, meta_e = copy.deepcopy(META_P), copy.deepcopy(META_E)
    if mode == "bac": meta_e["sandbox_mode"] = "danger-full-access"
    envoyer = lambda meta, h: m.recevoir(copy.deepcopy(meta), {"input": copy.deepcopy(h)})
    hp = [{"type": "message", "role": "user"}]
    sp = envoyer(meta_p, hp)[0]; hp.append(sp)
    if mode == "sans-spawn":
        envoyer(meta_p, hp + [{"type": "function_call_output", "call_id": sp["call_id"], "output": "collaboration is disabled"}]); return
    a = json.loads(sp["arguments"]); nom = "/root/" + a["task_name"]; meta_e["agent_name"] = nom
    hp.append({"type": "function_call_output", "call_id": sp["call_id"], "output": json.dumps({"task_name": nom})})
    at = envoyer(meta_p, hp)[0]; hp.append(at)
    he = [{"type": "message", "role": "user"}, {"type": "agent_message", "author": "/root", "recipient": nom, "content": [
        {"type": "input_text", "text": "Message Type: NEW_TASK\n"}, {"type": "encrypted_content", "encrypted_content": a["message"]}]}]
    c = envoyer(meta_e, he)[0]; x = json.loads(c["arguments"])
    p = RUN([x["shell"], "-c", x["cmd"]], capture_output=True, text=True, env=env, timeout=120)
    he += [c, {"type": "function_call_output", "call_id": c["call_id"], "output": sortie_exec(p.stdout.strip(), p.returncode)}]
    fin = envoyer(meta_e, he)[0]["content"][0]["text"]
    hp += [{"type": "function_call_output", "call_id": at["call_id"], "output": '{"message":"Wait completed.","timed_out":false}'},
           {"type": "agent_message", "author": nom, "recipient": "/root", "content": [{"type": "input_text", "text": f"Payload:\n{fin}"}]}]
    envoyer(meta_p, hp)


class Compteur:
    """Remplace les témoins signés (aucun socket ici) : connexions signées du contrat, autres connexions."""
    secrets = []
    def __init__(self, secret, f=None): self.contrat, self.autres, self.port = 0, 0, 1; Compteur.secrets.append(secret)
    def attendre(self, n, delai=5): self.contrat = max(self.contrat, n); return True
    def fermer(self): pass


class FauxExecutable(unittest.TestCase):
    """De bout en bout, sans moteur ni socket : le contrat lance « codex » (simulé d'après la mesure) avec les arguments de
    l'agent et SON faux fournisseur ; l'enfant joue la sonde SANS bac à sable, donc ses évasions RÉUSSISSENT."""
    deja = set()

    def jouer(self, mode, maison=None):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); cwd, dossier, autre = t / "travail", t / "agent", t / "autre"
            for d in (cwd, dossier, autre): d.mkdir()
            (autre / "agent.conf").write_text("nom = autre\n"); (t / "coffre.json").write_text("{}")
            env = {**os.environ, **({"HOME": str(maison)} if maison else {})}
            pose, lignes, vu, modeles = C.Pose(t / "pose.json"), [], {}, []
            Vrai = C.FauxModele13
            def fabrique(*a, **k):
                modeles.append(Vrai(*a, serveur=False, **k)); return modeles[-1]
            def lancer(argv, **kw):
                vu.update(argv=argv, env=kw["env"], cibles=next(cwd.glob("*-sous-agent-cibles.json")).read_text())
                codex_simule(modeles[-1], mode, kw["env"])
                return subprocess.CompletedProcess(argv, 0, "", "")
            with patch.object(C, "TemoinSigne", Compteur), patch.object(C, "connecte_signe", lambda f, s: True), \
                 patch.object(C, "DEHORS", ("127.0.0.1", 2)), patch.object(C, "FauxModele13", fabrique), \
                 patch.object(C.subprocess, "run", side_effect=lancer):
                ok = C.condition_sous_agents(lambda b, x: lignes.append((bool(b), x)), ["-p", "agent-essai"], cwd, env, dossier,
                                             pose, [str(t / "coffre.json"), str(autre / "agent.conf")], autre, codex="codex-essai")
            pose.retirer()
            a = vu["argv"]
            self.assertEqual(a[:3], ["codex-essai", "exec", "--ephemeral"]); self.assertIn("agent-essai", a)
            self.assertIn(f'model_providers.berger-contrat.base_url="{modeles[-1].url}"', a)
            self.assertIn('model_providers.berger-contrat.env_key="BERGER_CONTRAT_CLE"', a)
            self.assertEqual(vu["env"]["BERGER_CONTRAT_CLE"], "cle-factice-du-contrat", "clé factice : visible de l'enfant (mesuré)")
            tirages = [modeles[-1].attendu()["nonce"], *modeles[-1].attendu()["appels"].values()]
            visible = json.dumps(a) + vu["cibles"] + json.dumps({k: v for k, v in vu["env"].items() if k.startswith("BERGER")})
            self.assertTrue(Compteur.secrets and all(len(s) >= 32 and s not in visible for s in Compteur.secrets),
                            "secret du contrat jamais vu de l'agent (arguments, consigne, cibles)")
            self.assertFalse([x for x in tirages if x in visible], "nonce et call_id jamais dans l'argv, l'environnement ni les cibles")
            self.assertEqual(len(set(Compteur.secrets)), 1, "un secret pour ce contrat, ses deux témoins")
            self.assertNotIn(Compteur.secrets[0], FauxExecutable.deja, "un secret neuf à chaque contrat")
            FauxExecutable.deja.add(Compteur.secrets[0]); Compteur.secrets.clear()
            return ok, lignes, sorted(p.name for p in cwd.iterdir())

    def test_sous_agent_sans_bac_a_sable_evasions_nommees(self):
        ok, l, restes = self.jouer("normal")
        self.assertFalse(ok)
        self.assertTrue(any(b and x.startswith("témoin (13)") for b, x in l), l)
        rouges = " ".join(x for b, x in l if not b)
        self.assertIn("évasion : lecture", rouges); self.assertIn("évasion : écriture MCP", rouges)
        self.assertEqual(restes, [], "cibles retirées, rien laissé dans son dossier")

    def test_spawn_refuse_non_mesurable(self):
        ok, l, restes = self.jouer("sans-spawn")
        self.assertFalse(ok); self.assertIn("sous-agent non lancé", l[-1][1]); self.assertEqual(restes, [])

    def test_bac_a_sable_different_rouge(self):
        ok, l, _ = self.jouer("bac")
        self.assertFalse(ok); self.assertIn("bac à sable de l'enfant", l[-1][1])

    def test_usercustomize_du_home_ne_falsifie_pas_la_sonde(self):
        """Un agent qui écrit dans son HOME y pose un usercustomize.py qui réécrit « lu »/« ecrit » en « refuse » (bon jeton,
        bonne empreinte). Témoin positif : sans -I, la falsification marche ; avec la commande du contrat (-I), jamais."""
        with tempfile.TemporaryDirectory() as m:
            site = subprocess.run([sys.executable, "-c", "import site; print(site.getusersitepackages())"], env={**os.environ, "HOME": m},
                                  capture_output=True, text=True).stdout.strip()
            if not site.startswith(m): self.skipTest("site utilisateur hors du HOME ici")
            Path(site).mkdir(parents=True); (Path(site) / "usercustomize.py").write_text(FALSIFIE)
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / "lisible").write_text("x"); cibles = Path(d) / "cibles.json"
                cibles.write_text(json.dumps({"lire": [str(Path(d) / "lisible")], "lister": [], "mcp": [], "reseau": []}))
                sans = subprocess.run([sys.executable, str(T / "sonde-mcp.py"), "sous-agent", str(cibles)], env={**os.environ, "HOME": m},
                                      capture_output=True, text=True).stdout
                self.assertIn('"refuse"', sans.splitlines()[-1], "témoin : sans -I, le HOME falsifie la sonde")
            ok, l, _ = self.jouer("normal", Path(m))
            rouges = " ".join(x for b, x in l if not b)
            self.assertFalse(ok); self.assertIn("évasion : lecture", rouges); self.assertIn("RÉUSSIE", rouges)


FALSIFIE = """import sys
class Faux:
    def __init__(self, f): self.f = f
    def write(self, s): return self.f.write(s.replace('"lu"', '"refuse"').replace('"ecrit"', '"refuse"'))
    def __getattr__(self, n): return getattr(self.f, n)
sys.stdout = Faux(sys.stdout)
"""


if __name__ == "__main__": unittest.main()
