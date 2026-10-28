#!/usr/bin/env python3
"""Régression des frontières de demander ; aucune sentinelle imprimée."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SRC = Path(__file__).resolve().parent.parent


def charger(nom, fichier, env):
    if nom == 'demander' and 'repertoire_prive' not in env:
        charger('repertoire_prive', fichier, env)
    if nom == 'ecrire_profil_ouvert' and '_transport' not in env:   # (forme d'accès : la fonction vit dans bin/moteurs/codex.py, nom `transport`)
        import importlib.util
        spec = importlib.util.spec_from_file_location('transport_configuration', SRC / 'courtier/outils/_transport.py')
        transport = importlib.util.module_from_spec(spec); spec.loader.exec_module(transport)
        env['_transport'] = env['transport'] = transport
    if '_transport' not in env and 'subprocess' in env:
        env['_transport'] = SimpleNamespace(executer=lambda programme, args, **kw: env['subprocess'].run([programme, *args], **kw))
    arbre = ast.parse((SRC / fichier).read_text())
    fonction = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == nom)
    exec(compile(ast.Module(body=[fonction], type_ignores=[]), fichier, 'exec'), env)
    return env[nom]


def registre(env, coeur=(), famille=()):
    """Forme d'accès (modulaire, lot 3) : main() cherche ses verbes dans le registre des commandes. On lui donne le VRAI paquet bin/commandes/
    avec les fonctions de verbe extraites de leur fichier (même source) : `coeur` = verbes de bin/berger (inscrits par la famille de transition,
    donc avec leurs DROITS), `famille` = {verbe: fichier de sa famille}."""
    import importlib.util, sys
    sys.path.insert(0, str(SRC / 'bin'))
    spec = importlib.util.spec_from_file_location('commandes_essai', SRC / 'bin/commandes/__init__.py')
    c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
    nom = lambda v: 'verbe_' + v.replace('-', '_')
    for v in coeur: charger('_opt', 'bin/berger', env) if '_opt' not in env else None; charger(nom(v), 'bin/berger', env)
    ns = {'VERBES_COEUR': {v: env[nom(v)] for v in coeur}}
    exec(compile((SRC / 'bin/commandes/transition.py').read_text(), 'transition', 'exec'), ns)
    c.VERBES.update(ns['VERBES']); c.DROITS.update(ns['DROITS']); c.FAMILLE_DE.update({v: 'transition' for v in ns['VERBES']})
    for v, fichier in dict(famille).items():
        charger(nom(v), fichier, env); c.VERBES[v] = env[nom(v)]; c.DROITS[v] = {'prive': False, 'cas_go': None}; c.FAMILLE_DE[v] = Path(fichier).stem
        pa = [n for n in ast.parse((SRC / fichier).read_text()).body if isinstance(n, ast.Assign) and n.targets[0].id == 'PASSE']
        if pa: c.FAMILLES[Path(fichier).stem] = SimpleNamespace(PASSE=eval(compile(ast.Expression(pa[0].value), fichier, 'eval'), env))   # PASSE déclaré par la famille
    env['commandes'] = c


class Frontieres(unittest.TestCase):
    def test_demander(self):
        temoin = 'messageconfidentieltemoin'
        for moteur in ('codex', 'claude'):
            appels = []
            def lancer(argv, **kw):
                appels.append((argv, kw))
                if '-o' in argv:
                    sortie = Path(argv[argv.index('-o') + 1])
                    self.assertTrue(sortie.stat().st_mode & 0o777 == 0o600, 'droits fichier')
                    self.assertTrue(sortie.parent.stat().st_mode & 0o777 == 0o700, 'droits dossier')
                    sortie.write_text('reponse')
                return SimpleNamespace(returncode=0, stdout='reponse')
            env = dict(tempfile=SimpleNamespace(TemporaryDirectory=lambda **kw: tempfile.TemporaryDirectory(dir='/tmp', **kw),
                       NamedTemporaryFile=lambda **kw: tempfile.NamedTemporaryFile(**({'dir': '/tmp'} | kw))),
                       subprocess=SimpleNamespace(run=lancer, DEVNULL=subprocess.DEVNULL, TimeoutExpired=subprocess.TimeoutExpired),
                       os=__import__('os'), Path=Path, travail=lambda a: SRC, conf=lambda a: {'moteur': moteur},
                       ouvert=lambda a: True, moteurs=SimpleNamespace(args_moteur=lambda *a: []), env_agent=lambda *a: {},
                       env_codex=lambda a: {}, lire=lambda f: Path(f).read_text(), solliciter=lambda a: None)
            fonction = charger('demander', 'bin/berger', env)
            resultat = fonction('essai', temoin)
            self.assertTrue(resultat[:2] == ('reponse', moteur), 'parcours positif')
            self.assertTrue(all(temoin not in str(argv) for argv, _ in appels), 'contenu présent dans argv')
            self.assertTrue(appels[0][1].get('input') == temoin, 'entrée non transmise')
            sorties = [argv[argv.index('-o') + 1] for argv, _ in appels if '-o' in argv]
            self.assertTrue(all(not Path(f).exists() for f in sorties), 'sortie temporaire non nettoyée')


    def test_delegation(self):
        temoin = 'messageconfidentieltemoin'
        appels = []
        def lancer(argv, **kw):
            appels.append((argv, kw))
            return SimpleNamespace(returncode=1, stdout='')
        env = dict(EN_DELEGATION=set(), echange=lambda *a: None, BERGER=SRC,
                   reglage=lambda a, cle: 'strict' if cle == 'mur' else '',
                   subprocess=SimpleNamespace(run=lancer, TimeoutExpired=subprocess.TimeoutExpired))
        fonction = charger('deleguer', 'courtier/courtier', env)
        fonction('origine', 'cible', temoin, lambda *a: None)
        self.assertTrue(all(temoin not in str(argv) for argv, _ in appels), 'contenu dans argv imbriqué')
        self.assertTrue(temoin in appels[0][1].get('input', ''), 'texte imbriqué perdu')

    def test_entree_demander(self):
        import io
        temoin = 'messageconfidentieltemoin'
        appels = []
        env = dict(sys=SimpleNamespace(stdin=io.TextIOWrapper(io.BytesIO(temoin.encode())),
                                       stderr=io.StringIO(), exit=lambda code: None),
                   print=lambda *a, **kw: None,
                   demander=lambda *a: (appels.append(a) or ('reponse', 'claude', [])))
        for nom, fichier in (('entree_privee', 'bin/noyau/transport.py'), ('main', 'bin/berger')):
            source = ast.parse((SRC / fichier).read_text())
            if any(isinstance(n, ast.FunctionDef) and n.name == nom for n in source.body):
                charger(nom, fichier, env)
        registre(env, coeur=['demander'])
        env['main'](['demander', 'essai', '--stdin'])
        self.assertTrue(appels[0][1] == temoin, 'stdin CLI perdu')


    def test_processus_reels(self):
        import os
        import json
        import sys
        from unittest.mock import patch
        temoin = 'messageconfidentieltemoin'
        instructions = 'consignesystemeprivee'
        with tempfile.TemporaryDirectory() as temporaire:
            racine = Path(temporaire)
            code = ("#!" + sys.executable + "\n"
                    "import json, os, sys\nfrom pathlib import Path\n"
                    "texte = sys.stdin.read()\n"
                    "instructions = ''\n"
                    "if '-p' in sys.argv and Path(sys.argv[0]).name == 'codex':\n import tomllib\n instructions = tomllib.loads((Path(os.environ['CODEX_HOME']) / (sys.argv[sys.argv.index('-p') + 1] + '.config.toml')).read_text()).get('developer_instructions', '')\n"
                    "if '--append-system-prompt-file' in sys.argv: instructions = Path(sys.argv[sys.argv.index('--append-system-prompt-file') + 1]).read_text()\n"
                    "argv = Path('/proc/self/cmdline').read_bytes().split(bytes([0]))\n"
                    "with open(os.environ['TRACE'], 'a') as f: f.write(json.dumps({'argv': [a.decode() for a in argv], 'texte': texte, 'instructions': instructions}) + '\\n')\n"
                    "if os.environ.get('PANNE') == Path(sys.argv[0]).name: sys.exit(1)\n"
                    "if '-o' in sys.argv: Path(sys.argv[sys.argv.index('-o') + 1]).write_text('reponse')\n"
                    "else: print('reponse')\n")
            for moteur in ('codex', 'claude'):
                f = racine / moteur; f.write_text(code); f.chmod(0o700)
            env = dict(tempfile=tempfile, subprocess=subprocess, os=os, Path=Path,
                       travail=lambda a: racine, conf=lambda a: {'moteur': 'codex'}, ouvert=lambda a: True,
                       reglages_mission=lambda a: ('', ''), consigne_systeme=lambda a: instructions,
                       dossier=lambda a: racine, externe=lambda a: False, json=json, re=__import__("re"), CODEX_HOME=racine,
                       env_agent=lambda a, base=None: dict(base or os.environ),
                       env_codex=lambda a: dict(os.environ, CODEX_HOME=str(racine)), lire=lambda f: Path(f).read_text() if Path(f).exists() else '')
            import importlib.util
            spec = importlib.util.spec_from_file_location('transport_reel', SRC / 'courtier/outils/_transport.py')
            transport = importlib.util.module_from_spec(spec); spec.loader.exec_module(transport)
            env['_transport'] = env['transport'] = transport; env['solliciter'] = lambda a: None   # anti-boucle : hors sujet ici
            # forme d'accès (lot 2) : le code des moteurs vit dans bin/moteurs/ (codex.py, claude.py : args ; __init__.py : args_moteur)
            envs = {m: dict(env) for m in ('codex', 'claude')}
            charger('ecrire_profil_ouvert', 'bin/moteurs/codex.py', envs['codex'])
            for m, e in envs.items(): charger('args', f'bin/moteurs/{m}.py', e)
            env['module'] = lambda m: SimpleNamespace(args=envs[m]['args']); charger('args_moteur', 'bin/moteurs/__init__.py', env)
            env['moteurs'] = SimpleNamespace(args_moteur=env['args_moteur'])
            fonction = charger('demander', 'bin/berger', env)
            for moteur, panne in (('codex', ''), ('claude', ''), ('codex', 'codex')):
                trace = racine / 'trace'; trace.unlink(missing_ok=True)
                with patch.dict(os.environ, PATH=str(racine) + os.pathsep + os.environ['PATH'], TRACE=str(trace), PANNE=panne):
                    resultat = fonction('essai', temoin, moteur)
                traces = [json.loads(l) for l in trace.read_text().splitlines()]
                self.assertTrue(resultat[0] == 'reponse', 'réponse positive perdue')
                self.assertTrue(all(temoin not in str(t['argv']) for t in traces), 'cmdline exposé')
                self.assertTrue(all(t['texte'] == temoin for t in traces), 'stdin incomplet')
                self.assertTrue(all(instructions not in str(t['argv']) for t in traces), 'instructions système exposées')
                self.assertTrue(all(t['instructions'] == instructions for t in traces), 'instructions système perdues')
                self.assertTrue(len(traces) == (2 if panne else 1), 'bascule non mesurée')
                for t in traces:
                    if '-o' in t['argv']:
                        self.assertTrue(not Path(t['argv'][t['argv'].index('-o') + 1]).exists(), 'nettoyage absent')

    def test_arguments_mur_ouvert(self):
        import os
        import json
        instructions = 'consignesystemeprivee'
        with tempfile.TemporaryDirectory() as td:
            env = dict(conf=lambda a: {}, travail=lambda a: Path(td), ouvert=lambda a: True,
                       consigne_systeme=lambda a: instructions, json=json,
                       CODEX_HOME=Path(td), Path=Path, os=os, tempfile=tempfile, re=__import__("re"))
            charger('ecrire_profil_ouvert', 'bin/moteurs/codex.py', env)
            args = charger('args', 'bin/moteurs/codex.py', env)('essai')   # forme d'accès : Codex vit dans bin/moteurs/codex.py
            self.assertTrue(all(instructions not in a for a in args), 'instructions dans argv')

    def test_demander_sans_argument(self):
        import sys
        env = dict(sys=sys)
        fonction = charger('main', 'bin/berger', env)
        registre(env, coeur=['demander'])
        with self.assertRaises(SystemExit) as contexte:
            fonction(['demander'])
        self.assertTrue('berger demander' in str(contexte.exception), 'usage absent')

    def test_refus_positionnel(self):
        import sys
        appels = []
        env = dict(sys=sys, demander=lambda *a: appels.append(a))
        fonction = charger('main', 'bin/berger', env)
        registre(env, coeur=['demander'])
        with self.assertRaises(ValueError):
            fonction(['demander', 'essai', 'messageconfidentieltemoin'])
        self.assertTrue(not appels, 'ancien transport encore accepté')

    def test_entree_bornee(self):
        import io, importlib.util
        spec = importlib.util.spec_from_file_location('ecarts_essai', SRC / 'bin/noyau/ecarts.py')   # le VRAI Refus (forme d'accès : entree_privee le cite depuis le lot 3 bis)
        ecarts = importlib.util.module_from_spec(spec); spec.loader.exec_module(ecarts)
        for octets in (b'a' * (1024 * 1024 + 1), bytes([255])):
            env = dict(sys=SimpleNamespace(stdin=io.TextIOWrapper(io.BytesIO(octets))), Refus=ecarts.Refus)
            fonction = charger('entree_privee', 'bin/noyau/transport.py', env)
            with self.assertRaises(ValueError) as e: fonction()
            self.assertTrue(isinstance(e.exception, ecarts.Refus), 'refus d\'entrée explicite (Refus, sous-classe de ValueError)')

    def test_nettoyage_exception(self):
        import os
        for erreur in (subprocess.TimeoutExpired('essai', 1), KeyboardInterrupt()):
            sorties = []
            def lancer(argv, **kw):
                if '-o' in argv: sorties.append(argv[argv.index('-o') + 1])
                raise erreur
            env = dict(tempfile=tempfile, subprocess=SimpleNamespace(run=lancer, TimeoutExpired=subprocess.TimeoutExpired),
                       os=os, Path=Path, travail=lambda a: SRC, conf=lambda a: {'moteur': 'codex'}, ouvert=lambda a: True,
                       moteurs=SimpleNamespace(args_moteur=lambda *a: []), env_agent=lambda *a: {}, env_codex=lambda a: {}, solliciter=lambda a: None)
            fonction = charger('demander', 'bin/berger', env)
            try: fonction('essai', 'messageconfidentieltemoin')
            except KeyboardInterrupt: pass
            self.assertTrue(sorties and all(not Path(f).exists() for f in sorties), 'nettoyage après interruption absent')


    def test_notifications_generiques(self):
        import datetime
        temoin = 'messageconfidentieltemoin'
        with tempfile.TemporaryDirectory() as temporaire:
            racine = Path(temporaire); (racine / 'courtier').mkdir()
            appels = []
            def lancer(argv, **kw):
                appels.append(argv); return SimpleNamespace(returncode=0)
            env = dict(shutil=SimpleNamespace(which=lambda x: x), NOTIFY_SEND='notify-send', HERDR='herdr',
                       subprocess=SimpleNamespace(run=lancer, TimeoutExpired=subprocess.TimeoutExpired),
                       BERGER=racine, datetime=datetime)
            fonction = charger('notifier', 'bin/noyau/bandeaux.py', env)   # (forme d'accès : la fonction vit dans le noyau depuis le lot 3 bis)
            fonction(temoin, temoin, urgent=True)
            self.assertTrue(all(temoin not in str(argv) for argv in appels), 'notification privée dans argv')
            self.assertTrue(temoin in (racine / 'courtier/notifications.log').read_text(), 'contenu du panneau perdu')


    def test_notification_imbriquee(self):
        import json
        temoin = 'messageconfidentieltemoin'
        appels = []
        env = dict(BERGER=SRC, json=json, subprocess=SimpleNamespace(run=lambda argv, **kw: appels.append((argv, kw))))
        fonction = charger('notifier_proprietaire', 'courtier/courtier', env)
        fonction(temoin, temoin)
        self.assertTrue(all(temoin not in str(argv) for argv, _ in appels), 'titre dans argv imbriqué')
        self.assertTrue(json.loads(appels[0][1]['input']) == [temoin, temoin], 'notification imbriquée perdue')

    def test_journal_sur_stdin(self):
        import io
        temoin = 'contenupriveessai'
        appels = []
        env = dict(sys=SimpleNamespace(stdin=io.TextIOWrapper(io.BytesIO(temoin.encode()))),
                   os=SimpleNamespace(environ={'BERGER_AGENT': 'essai'}),
                   journal=lambda *a: appels.append(a), print=lambda *a, **kw: None, Refus=ValueError)   # Refus : le nom de l'API que la famille `journal` emploie
        charger('entree_privee', 'bin/noyau/transport.py', env)
        fonction = charger('main', 'bin/berger', env)
        registre(env, famille={'noter': 'bin/commandes/journal.py'})   # (forme d'accès : `noter` est dans sa famille depuis le lot 3 bis)
        fonction(['noter', '--stdin'])
        self.assertTrue(appels == [('essai', temoin)], 'journal stdin perdu')
        with self.assertRaises(ValueError): fonction(['noter', temoin])


    def test_sigterm(self):
        import os
        import sys
        import time
        import signal
        with tempfile.TemporaryDirectory() as temporaire:
            trace = Path(temporaire) / 'trace'
            code = ("import ast, os, tempfile, time\nfrom pathlib import Path\n"
                    "arbre=ast.parse(Path(os.environ['SOURCE']).read_text())\n"
                    "fonction=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='repertoire_prive')\n"
                    "exec(compile(ast.Module(body=[fonction],type_ignores=[]),'essai','exec'))\n"
                    "with repertoire_prive() as d:\n"
                    " Path(os.environ['TRACE']).write_text(d)\n"
                    " time.sleep(60)\n")
            p = subprocess.Popen([sys.executable, '-'], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, env=dict(os.environ, SOURCE=str(SRC / 'bin/berger'), TRACE=str(trace)))
            try:
                p.stdin.write(code.encode()); p.stdin.close()
                fin = time.monotonic() + 10
                while not trace.exists() and time.monotonic() < fin: time.sleep(0.02)
                self.assertTrue(trace.exists(), 'processus de mesure absent')
                dossier = Path(trace.read_text())
                p.send_signal(signal.SIGTERM); p.wait(timeout=10)
                self.assertTrue(p.returncode == 143 and not dossier.exists(), 'SIGTERM sans nettoyage')
            finally:
                if p.poll() is None: p.kill(); p.wait()

    def test_recette_sans_agent_reel(self):
        import contextlib
        import io
        import json
        import os
        import runpy
        import hashlib
        from unittest.mock import patch
        recette = runpy.run_path(str(SRC / 'tests/sonde-herdr-lecture.py'), run_name='essai')['recette']
        for scenario in ('lecture', 'refus'):
            with tempfile.TemporaryDirectory() as temporaire:
                racine = Path(temporaire)
                faux = {'agents': lambda: ['essai'], 'dossier': lambda a: racine, 'travail': lambda a: racine,
                        'herdr_ids': lambda a: {'agents': {'codex': 'pane'}}, 'au_repos': lambda p: True, 'HERDR': 'herdr'}
                def remettre(methode, params, strict=False):
                    self.assertTrue(methode == 'agent.prompt' and params['target'] == 'essai-codex' and strict,
                                    'méthode de remise de recette incorrecte')
                    nom = next(w for w in params['text'].split() if w.endswith('/message.md'))
                    message = racine / nom
                    temoin = message.read_text().split('temoin: ')[1].strip()
                    self.assertTrue(temoin not in params['text'], 'valeur de recette dans l’invite')
                    self.assertTrue(message.stat().st_mode & 0o777 == 0o600, 'droits message de recette')
                    if scenario == 'lecture':
                        fd = os.open(message.parent / 'recu', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                        with os.fdopen(fd, 'w') as f: f.write(hashlib.sha256(temoin.encode()).hexdigest())
                        message.unlink()
                    else: raise ValueError('remise refusée')
                    return {}
                faux['herdr_api'] = remettre
                with patch.dict(recette.__globals__, runpy=SimpleNamespace(run_path=lambda *a, **kw: faux)), contextlib.redirect_stdout(io.StringIO()):
                    if scenario == 'lecture': recette(['essai', 'codex'])
                    else:
                        with self.assertRaises(ValueError): recette(['essai', 'codex'])
                self.assertTrue(not list(racine.iterdir()), 'fichiers de recette oubliés')


if __name__ == '__main__':
    resultat = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Frontieres))
    if resultat.wasSuccessful():
        for numero in range(resultat.testsRun): print('ok contrôle argv privé', numero + 1)
    raise SystemExit(0 if resultat.wasSuccessful() else 1)
