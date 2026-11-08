#!/usr/bin/env python3
"""Contrôle (12) : rejeu des requêtes capturées, sans moteur, socket, réseau ni installation vivante."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util, json, unittest
from pathlib import Path
from unittest.mock import patch

T = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("contrat", T / "contrat-moteur.py")
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
CONNUS = C.charger_connus("codex", "0.165.0")
FX = json.loads((T / "fixtures/codex-0.165.0-requetes.json").read_text())["requetes"]
FONCTION = {"type": "function", "name": "exec_command"}
COMPLET = {"tools": [FONCTION]}
TEMOIN = FX["gpt-5.5-sans-reglage"]


def verdict(corps, temoin=None):
    """Même collecte et même verdict que le fournisseur ; seul le transport est remplacé."""
    class Fournisseur:
        url = "http://fournisseur.invalid/v1"
        def __init__(self): self.corps = []
        def fermer(self): pass
    f = Fournisseur()
    def lancer(args, **kw):
        f.corps = corps if 'web_search="disabled"' in args else (temoin or [TEMOIN])
    lignes = []
    with patch.object(C, "FauxFournisseur", return_value=f), patch.object(C.subprocess, "run", side_effect=lancer):
        C.condition_web_codex(lambda ok, txt: lignes.append((ok, txt)), C.RECHERCHE_CODEX, T, {}, CONNUS, set())
    return lignes


class Mesure(unittest.TestCase):
    def test_captures_et_identifiants_structures(self):
        ancien = C.ids_requete(FX["gpt-5.5-avec-reglage"])
        nouveau = C.ids_requete(FX["defaut-avec-reglage"])
        self.assertIn((("function", "exec_command"),), ancien)
        self.assertIn((("namespace", "functions"), ("custom", "exec")), nouveau)
        self.assertIn((("namespace", "collaboration"), ("function", "spawn_agent")), nouveau)
        self.assertTrue(all(ok for ok, _ in verdict([FX["gpt-5.5-avec-reglage"]])))
        r = verdict([FX["defaut-avec-reglage"]])
        self.assertFalse(r[1][0]); self.assertIn("collaboration", r[1][1])

    def test_deux_emplacements_et_plusieurs_blocs(self):
        rq = {"tools": [FONCTION], "input": [
            {"type": "additional_tools", "tools": [{"type": "function", "name": "write_stdin"}]},
            {"type": "message", "role": "user"},
            {"type": "additional_tools", "tools": [{"type": "web_search"}]}]}
        self.assertEqual(len(C.ids_requete(rq)), 3)
        r = verdict([rq]); self.assertFalse(r[1][0]); self.assertIn("web_search", r[1][1])

    def test_enveloppe_inconnue_ne_disparait_pas(self):
        for rq, nom in (({"input": [{"type": "additional_tools_v2", "tools": [FONCTION]}]}, "additional_tools_v2"),
                        ({"input": {"type": "additional_tools", "tools": [FONCTION]}}, "input"),
                        ({"input": [None]}, "input[0]"),
                        ({"input": [{"tools": [FONCTION]}]}, "input[0]"),
                        ({"input": [{"type": "message", "tools": [FONCTION]}]}, "input[0]")):
            for corps in ([rq, COMPLET], [{**COMPLET, **rq}]):
                with self.subTest(rq=rq, corps=corps):
                    r = verdict(corps)
                    self.assertFalse(r[1][0]); self.assertIn("non mesurable", r[1][1]); self.assertIn(nom, r[1][1])

    def test_outil_mal_forme_nomme(self):
        for outil, nom in (({"type": "local_shell"}, "local_shell"),
                           ({"type": "function", "name": "exec_command", "tools": [FONCTION]}, "exec_command"),
                           ({"type": "custom"}, "custom"),
                           ({"type": "namespace", "name": "functions"}, "functions"),
                           ({"type": "function", "name": []}, "function")):
            with self.subTest(outil=outil):
                r = verdict([{"input": [{"type": "additional_tools", "tools": [FONCTION, outil]}]}])
                self.assertFalse(r[1][0]); self.assertIn("non mesurable", r[1][1]); self.assertIn(nom, r[1][1])

    def test_temoin_mal_forme_ne_prouve_rien(self):
        for rq, nom in (({"input": [{"type": "additional_tools_v2"}]}, "additional_tools_v2"),
                        ({"tools": [{"type": "local_shell"}]}, "local_shell"), ({}, "requête")):
            with self.subTest(rq=rq):
                r = verdict([COMPLET], [TEMOIN, rq])
                self.assertFalse(any(ok for ok, _ in r)); self.assertIn(nom, r[0][1])

    def test_namespace_ne_se_confond_pas_avec_un_nom(self):
        rq = {"input": [{"type": "additional_tools", "tools": [
            {"type": "namespace", "name": "functions", "tools": [{"type": "custom", "name": "exec"}]},
            {"type": "namespace", "name": "autre", "tools": [{"type": "custom", "name": "exec"}]}]}]}
        ids = C.ids_requete(rq)
        self.assertEqual(len(set(ids)), 4)
        r = verdict([rq]); self.assertFalse(r[1][0]); self.assertIn("namespace:autre/custom:exec", r[1][1])

    def test_liste_incomplete_a_cote_d_une_complete(self):
        for rq in ({**COMPLET, "input": [{"type": "additional_tools", "tools": []}]},
                   {"tools": None, "input": [{"type": "additional_tools", "tools": [FONCTION]}]}):
            with self.subTest(rq=rq):
                r = verdict([rq]); self.assertFalse(r[1][0]); self.assertIn("non mesurable", r[1][1])

    def test_annexe_connue_et_dedoublonnage(self):
        self.assertTrue(all(ok for ok, _ in verdict([{"input": "titre"}, COMPLET, COMPLET])))


if __name__ == "__main__": unittest.main()
