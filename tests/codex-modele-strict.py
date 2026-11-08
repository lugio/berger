#!/usr/bin/env python3
"""Modèle Codex fixé : vrais arguments de lancement dans une installation jetable, aucun moteur ni réseau."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import _produit
import json, subprocess, tempfile, unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent


class ModeleStrict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.tmp.cleanup)
        t = Path(cls.tmp.name); _produit.copier(SRC, t)
        (t / "config.toml").write_text('proprietaire = "Essai"\nmasques = []\n')
        for a, mur in (("strict", "strict"), ("ouvert", "ouvert")):
            d = t / "agents" / a; d.mkdir(parents=True)
            (d / "agent.conf").write_text(f"nom = {a}\nmoteur = codex\nmur = {mur}\n")
        programme = r'''
import contextlib, io, json, runpy, sys
from pathlib import Path
sys.argv = ['berger']
g = runpy.run_path('bin/berger', run_name='essai')['lancer'].__globals__
M = g['moteurs']; config = g['CONFIG']; out = {}
g['exiger_bac_a_sable'] = lambda a: None
mission = Path('agents/strict/MISSION.md')
def args(a='strict', m='codex', inter=True):
    try: return M.args_moteur(a, m, inter)
    except (SystemExit, ValueError) as e: return 'REFUS ' + str(e)
out['absente'] = args()
config['codex_modele_strict'] = 'gpt-5.5'
out['interactif'] = args(); out['exec'] = args(inter=False); out['ouvert'] = args('ouvert')
sortie = io.StringIO()
with contextlib.redirect_stdout(sortie): g['arguments_pont'](['strict', 'codex', '--non-interactif', '--contrat'])
out['contrat'] = json.loads(sortie.getvalue())['args']
mission.write_text('moteur : codex · modèle : gpt-5.5\nniveau : gros · raison : essai · effort : high\n')
out['mission_identique'] = args()
mission.write_text('moteur : codex · modèle : gpt-autre\n')
out['mission_differente'] = args()
del config['codex_modele_strict']; out['mission_sans_option'] = args()
config['codex_modele_strict'] = 'gpt-5.5'
mission.write_text('moteur : claude · modèle : sonnet\n')
out['mission_autre_moteur'] = args(); out['claude'] = args(m='claude')
mission.unlink()
out['invalides'] = []
for v in ('', ' ', '--help', 'gpt 5', 'gpt-5.5\n', 3, False, [], {}):
    config['codex_modele_strict'] = v; out['invalides'].append(args())
out['ouvert_option_invalide'] = args('ouvert')
print(json.dumps(out))
'''
        env = {**os.environ, "HOME": str(t), "BERGER_DIR": str(t), "BERGER_TMP_AGENTS": str(t / "temp-agents")}
        r = subprocess.run([sys.executable, "-c", programme], cwd=t, env=env, capture_output=True, text=True)
        if r.returncode: raise AssertionError(r.stderr)
        cls.out = json.loads(r.stdout)

    def test_absence_et_mur_ouvert(self):
        for k in ('absente', 'ouvert', 'ouvert_option_invalide'):
            self.assertIsInstance(self.out[k], list); self.assertNotIn('-m', self.out[k])

    def test_tous_les_lancements_stricts(self):
        for k in ('interactif', 'exec', 'contrat', 'mission_identique', 'mission_autre_moteur'):
            with self.subTest(k=k):
                a = self.out[k]; self.assertEqual(a.count('-m'), 1)
                self.assertEqual(a[a.index('-m') + 1], 'gpt-5.5')
                self.assertIn('web_search="disabled"', a); self.assertIn('features.multi_agent=false', a)
        self.assertIn('model_reasoning_effort=high', self.out['mission_identique'])

    def test_conflit_de_mission_refuse(self):
        r = self.out['mission_differente']
        self.assertIsInstance(r, str); self.assertIn('REFUS', r)
        self.assertIn('gpt-5.5', r); self.assertIn('gpt-autre', r)
        a = self.out['mission_sans_option']; self.assertEqual(a[a.index('-m') + 1], 'gpt-autre')

    def test_configuration_invalide_refusee(self):
        for r in self.out['invalides']:
            self.assertIsInstance(r, str); self.assertIn('REFUS', r); self.assertIn('codex_modele_strict', r)

    def test_claude_inchange(self):
        a = self.out['claude']; self.assertNotIn('-m', a)
        self.assertEqual(a[a.index('--model') + 1], 'sonnet')


if __name__ == '__main__': unittest.main()
