#!/usr/bin/env python3
"""Coffre de sessions factices : fichiers temporaires, aucun réseau."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

p = Path(__file__).resolve().parents[1] / 'courtier/_web_session.py'
spec = importlib.util.spec_from_file_location('web_session', p)
W = importlib.util.module_from_spec(spec)
if p.exists(): spec.loader.exec_module(W)

class Sessions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'coffre.json'
        self.path.write_text(json.dumps({'autre': {'conserve': True}}))
        self.backups = []
        self.s = W.SessionCoffre(self.path, lambda: self.backups.append(self.path.read_bytes()), horloge=lambda: 100)

    def etat(self):
        return {'cookies': [dict(name='session', value='temoinfactice', domain='.permis.test', path='/', secure=True, expires=-1)],
                'origins': [dict(origin='https://app.permis.test', localStorage=[dict(name='jeton', value='localfactice')])]}

    def save(self, etat=None):
        self.s.enregistrer('app.permis.test', 'agent', etat or self.etat(), 200)

    def test_valeurs_session_liees_identite_et_retenues(self):
        self.save()
        self.assertEqual(self.s.valeurs_session('app.permis.test','agent'),{'temoinfactice','localfactice'})
        self.assertEqual(self.s.valeurs_session('app.permis.test','autre'),set())
        self.assertEqual(self.s.valeurs_session('ailleurs.test','agent'),set())
        self.s.effacer('app.permis.test')
        self.assertEqual(self.s.valeurs_session('app.permis.test','agent'),{'temoinfactice','localfactice'})

    def test_ecriture_lecture_et_sauvegarde(self):
        self.save()
        self.assertEqual(len(self.backups), 1)
        self.assertEqual(self.s.lire('app.permis.test', 'agent')['agent'], 'agent')
        self.assertIsNone(self.s.lire('app.permis.test', 'autre'))
        self.assertTrue(json.loads(self.path.read_text())['autre']['conserve'])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.s.horloge = lambda: 201
        self.assertIsNone(self.s.lire('app.permis.test'))

    def test_cookies_exact_path_secure_expiry_et_origines(self):
        e = self.etat(); base = e['cookies'][0]
        e['cookies'] += [dict(base, name='long', path='/admin', value='longfactice'),
                         dict(base, name='mort', expires=90), dict(base, name='etranger', domain='ailleurs.test'),
                         dict(base, name='injection', value='bad; value'), dict(base, name='bad\r\n', value='x')]
        e['origins'].append(dict(origin='https://ailleurs.test', localStorage=[dict(name='x', value='etrangerfactice')]))
        self.save(e)
        self.assertEqual(self.s.cookie('app.permis.test', '/admin/x'), 'long=longfactice; session=temoinfactice')
        self.assertEqual(self.s.cookie('app.permis.test', '/administrator'), 'session=temoinfactice')
        self.assertEqual(self.s.cookie('app.permis.test', secure=False), '')
        self.assertEqual(self.s.cookie('autre.permis.test'), '')
        self.assertEqual(self.s.valeurs(), {'temoinfactice', 'longfactice', 'localfactice'})
        self.assertEqual(len(self.s.lire('app.permis.test')['etat']['origins']), 1)

    def test_effacement_idempotent_valeurs_retenues_et_repr(self):
        self.save(); self.assertTrue(self.s.effacer('app.permis.test'))
        self.assertFalse(self.s.effacer('app.permis.test'))
        self.assertEqual(len(self.backups), 2)
        self.assertIsNone(self.s.lire('app.permis.test'))
        self.assertIn('localfactice', self.s.valeurs())
        self.assertNotIn('temoinfactice', repr(self.s))
        self.assertTrue(json.loads(self.path.read_text())['autre']['conserve'])

    def test_backup_echec_sans_mutation_et_retour_zero_accepte(self):
        before = self.path.read_bytes()
        def refuse(): raise RuntimeError('refus')
        self.s.sauvegarder = refuse
        with self.assertRaises(RuntimeError): self.save()
        self.assertEqual(self.path.read_bytes(), before)
        self.s.sauvegarder = lambda: 0
        self.save(); self.assertIsNotNone(self.s.lire('app.permis.test'))

    def test_domaines_et_bornes(self):
        for d in ['127.0.0.1', '*.permis.test', 'permis.test:443', 'localhost', 'permis.test\n']:
            with self.subTest(d=d), self.assertRaises(ValueError): self.s.enregistrer(d, 'agent', self.etat(), 200)
        e = self.etat(); e['origins'][0]['localStorage'][0]['value'] = 'x' * (1024 * 1024)
        with self.assertRaises(ValueError): self.save(e)
        self.assertEqual(self.backups, [])

    def test_relecture_independante_copie_et_absence_mutation(self):
        self.save()
        autre = W.SessionCoffre(self.path, lambda: 0, horloge=lambda: 100)
        avant = self.path.read_bytes()
        entree = autre.lire('app.permis.test')
        entree['etat']['cookies'][0]['value'] = 'modifie'
        self.assertEqual(autre.cookie('app.permis.test'), 'session=temoinfactice')
        self.assertEqual(autre.valeurs(), {'temoinfactice', 'localfactice'})
        self.assertEqual(self.path.read_bytes(), avant)
        self.save()
        self.assertEqual(len(self.backups), 1)

    def test_cookie_reserve_a_agent_de_session(self):
        self.save()
        self.assertEqual(self.s.cookie('app.permis.test', agent='autre'), '')
        self.assertEqual(self.s.cookie('app.permis.test', agent='agent'), 'session=temoinfactice')
        self.assertEqual(self.s.cookie('app.permis.test'), 'session=temoinfactice')

    def test_header_borne_et_controles_refuses(self):
        e = self.etat(); base = e['cookies'][0]
        e['cookies'] = [dict(base, name='a', value='x' * 5000), dict(base, name='b', value='y' * 5000)]
        for valeur in ['bad\r', 'bad\n', 'bad\x00', 'bad;rest', 'bad"', 'bad\\rest', 'bad rest']:
            e['cookies'].append(dict(base, value=valeur))
        self.save(e)
        header = self.s.cookie('app.permis.test')
        self.assertLessEqual(len(header), W.COOKIE_MAX)
        self.assertNotIn('session=', header)

    def test_liens_coffre_et_verrou_refuses(self):
        original = self.path.read_bytes()
        other = self.path.with_name('autre'); other.write_bytes(original)
        self.path.unlink(); self.path.symlink_to(other)
        with self.assertRaises((ValueError, OSError)): self.save()
        self.path.unlink(); self.path.write_bytes(original)
        lock = self.path.with_name(self.path.name + '.lock')
        lock.unlink(missing_ok=True); lock.symlink_to(other)
        with self.assertRaises((ValueError, OSError)): self.save()
        self.assertEqual(other.read_bytes(), original)

if __name__ == '__main__': unittest.main()
