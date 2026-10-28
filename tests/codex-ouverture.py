#!/usr/bin/env python3
"""Vraie CLI mission, double Herdr CLI/socket ; aucun moteur ni serveur réel.
Les témoins sont comparés sans jamais les afficher, même en cas d'échec.
"""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import ast
import json
import importlib.util
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1]
# La socket est remplacée, le récepteur est un vrai processus alimenté sur stdin.
LANCEUR = r'''
import json,os,runpy,socket,subprocess,sys
from pathlib import Path
class Socket:
 def __init__(self,*a): self.response=b''
 def __enter__(self): return self
 def __exit__(self,*a): pass
 def settimeout(self,*a): pass
 def connect(self,*a): pass
 def sendall(self,b):
  r=subprocess.run([sys.executable,os.environ['FAUX'],'socket'],input=b,capture_output=True,check=True)
  self.response=r.stdout
 def recv(self,n):
  b,self.response=self.response[:n],self.response[n:];return b
socket.socket=Socket
sys.argv=[os.environ['SOURCE'],'--stdin']
with open(os.environ['TRACE'],'a') as trace:
 trace.write(json.dumps({'argv':Path('/proc/self/cmdline').read_bytes().decode().split(chr(0)), 'method':None,'args':[]})+'\n')
g=runpy.run_path(sys.argv[0],run_name='essai')
f=g['mission'].__globals__
# Seul sleep fait avancer l'horloge : le coût des processus Python ne consomme
# aucun délai simulé. Les scénarios progressent par lectures, pas par secondes réelles.
import time as temps_reel
class Horloge:
 def __init__(self):self.maintenant=0
 def monotonic(self):return self.maintenant
 def sleep(self,n):self.maintenant+=n
 def __getattr__(self,nom):return getattr(temps_reel,nom)
c=g['moteurs'].MODULES['codex'].__dict__   # forme d'accès (lot 2) : l'ouverture de Codex vit dans bin/moteurs/codex.py
f['time']=c['time']=Horloge()
c['CODEX_OUVERTURE_DELAI']=5
c['CODEX_RECEPTION_DELAI']=3
c['CODEX_SCRUTATION']=1
f['journal']=lambda *a:None
f['echange']=lambda *a:None
f['agent_vivant']=lambda *a:False
f['espace_ouvert']=lambda *a:False
# Le lancement seul est doublé : la vraie mission doit gérer le dialogue et la remise.
def lancer(a,*args):
 (f['dossier'](a)/'.herdr.json').write_text(json.dumps({'agents':{os.environ['MOTEUR']:'panneau'}}))
f['espace']=lancer
f['main'](sys.argv[1:])
'''
FAUX = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
state=Path(os.environ['ETAT']);d=json.loads(state.read_text())
args=sys.argv[1:];req=None
if args==['socket']:req=json.load(sys.stdin)
with open(os.environ['TRACE'],'a') as f:
 f.write(json.dumps({'argv':Path('/proc/self/cmdline').read_bytes().decode().split(chr(0)),
                     'method':req['method'] if req else None,'args':args})+'\n')
mode=os.environ['SCENARIO'];text='';result={}
if req:
 if req['method']!='agent.prompt':raise SystemExit(1)
 d['envois']+=1
 d['invite']=req['params']['text']
 if not d['prete']:d['trop_tot']=True
 d['exact']=(req['params']['text'].startswith('Nouvelle mission de origine : lis MISSION.md') and
             req['params']['target']=='essai-'+os.environ['MOTEUR'])
 d['socket']=True
 if mode=='refus':
  print(json.dumps({'id':'berger','error':{'message':req['params']['text']}}));state.write_text(json.dumps(d));raise SystemExit()
 if mode not in ('perdu','retour-question','echo-idle','echo-tardif','working-tardif','saisie') and not (mode=='reessai' and d['envois']==1):d['travaille']=True
 if mode=='retour-question':d['prete']=False
elif args[:2]==['pane','read']:
 d['lectures']+=1
 if d['envois']:d['lectures_reception']=d.get('lectures_reception',0)+1
 if mode=='absent':result={'text':'› Explain this codebase'}
 elif mode=='lecture':result={}
 elif mode=='inconnu':result={'text':'Hooks need review\n› Trust all'}
 elif mode in ('hooks-option','hooks-question-citee'):
  result={'text':'Hooks need review\n› 1. Open restricted\n  2. Quit\n  enter continue · esc quit'}
  if mode=='hooks-question-citee':result['text']='Hooks need review\nTrust this folder?\n› 1. Trust and continue\n  2. Open restricted'
 elif mode=='retard' and d['lectures']<3:result={'text':'Starting…'}
 elif mode=='jamais':result={'text':'Starting…'}
 elif mode=='invite-retardee' and d['prete'] and d['lectures']<4:result={'text':'Starting…'}
 elif not d['prete']:
  result={'text':Path(os.environ['FIXTURE']).read_text()}
  if mode=='ambigu':result['text']+='\n  3. Open restricted'
  if mode=='banniere':result['text']='OpenAI Codex 0.163.0\n\n'+result['text']
  if mode=='selection-quit':result['text']=result['text'].replace('› 1.','  1.').replace('  2. Quit','› 2. Quit')
 else:
  result={'text':'OpenAI Codex\n› Explain this codebase\n? for shortcuts'}
  if mode=='mention':result['text']='Information : Open restricted\n'+result['text']
  if d['envois'] and (mode=='echo-idle' or (mode=='echo-tardif' and d['lectures_reception']>=4)):
   import textwrap
   result['text']='› '+textwrap.fill(d['invite'],width=40)+'\nRéponse\n'+result['text']
  if mode=='saisie' and d['envois']:result['text']='OpenAI Codex\n› '+d['invite']+'\n? for shortcuts'
elif args[:2]==['pane','get']:
 if mode=='working-tardif' and d.get('lectures_reception',0)>=4:d['travaille']=True
 result={'pane':{'agent_status':'working' if d['travaille'] else 'idle'}}
elif args[:2]==['agent','list']:
 d['listes']=d.get('listes',0)+1
 result={'agents':[] if mode=='absent' or (mode=='enregistrement-retarde' and d['listes']<3) else [{'name':'essai-'+os.environ['MOTEUR'],'pane_id':'panneau'}]}
elif args[:2]==['pane','send-keys']:
 d['touches'].extend(args[3:])
 if args[3:]==['enter'] and mode!='dialogue-bloque':d['prete']=True
 else:d['mauvais_choix']=True
state.write_text(json.dumps(d))
print(json.dumps({'id':'berger','result':result}) if req else json.dumps({'result':result}))
'''

class Ouverture(unittest.TestCase):
 def jouer(self,scenario,moteur='codex',strict=True):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);installation=root/'installation';a=installation/'agents/essai';a.mkdir(parents=True)
   (installation/'config.toml').write_text('proprietaire = "essai"\nmasques = []\n')
   (a/'agent.conf').write_text('nom = essai\nmoteur = '+moteur+'\nmur = '+('strict' if strict else 'ouvert')+'\nprojet = equipe\nsujet = essai\n')
   profil=installation/'.codex/essai.config.toml';profil.parent.mkdir()
   configuration='[projects.essai]\ntrust_level = \"untrusted\"\n'
   profil.write_text(configuration)
   faux=root/'herdr';faux.write_text(FAUX);faux.chmod(0o700)
   state=root/'etat';trace=root/'trace'
   state.write_text(json.dumps(dict(prete=scenario in ('prete','mention'),envois=0,lectures=0,touches=[],travaille=False)))
   env=dict(os.environ,HOME=str(root),BERGER_DIR=str(installation),BERGER_HERDR=str(faux),
            BERGER_HERDR_SOCKET=str(root/'socket'),FAUX=str(faux),SOURCE=str(SRC/'bin/berger'),
            ETAT=str(state),TRACE=str(trace),SCENARIO=scenario,MOTEUR=moteur,
            FIXTURE=str(SRC/'tests/fixtures/codex-confiance-0.163.0.txt'))
   temoin='contenuprivedelamission'
   r=subprocess.run([sys.executable,'-c',LANCEUR],input=json.dumps(['mission','essai',temoin,'--par','origine']),
                    capture_output=True,text=True,env=env,timeout=120)
   d=json.loads(state.read_text());ds=[json.loads(l) for l in trace.read_text().splitlines()] if trace.exists() else []
   self.assertTrue(all(temoin not in arg and 'Nouvelle mission' not in arg for x in ds for arg in x['argv']),'texte privé dans argv')
   self.assertTrue(temoin not in r.stdout+r.stderr,'témoin affiché')
   self.assertTrue((a/'MISSION.md').is_file(),'mission perdue sur disque')
   self.assertTrue(profil.read_text()==configuration,'confiance enregistrée modifiée')
   self.assertLess(d['lectures'],30,'scrutation non bornée')
   return r,d,ds
 def succes(self,scenario,envois=1):
  r,d,ds=self.jouer(scenario)
  self.assertTrue(r.returncode==0 and 'mission confiée' in r.stdout,'mission en échec')
  self.assertTrue(d['envois']==envois and d.get('exact') and d.get('socket'),'remise incorrecte')
  self.assertFalse(d.get('trop_tot') or d.get('mauvais_choix'),'mission avant invite ou confiance modifiée')
  self.assertTrue(d['travaille'],'réception non confirmée')
  return d
 def test_dialogue(self):self.assertEqual(self.succes('dialogue')['touches'],['enter'])
 def test_dialogue_apres_banniere(self):self.assertEqual(self.succes('banniere')['touches'],['enter'])
 def test_invite_deja_prete(self):self.assertEqual(self.succes('prete')['touches'],[])
 def test_mention_dans_conversation(self):self.assertEqual(self.succes('mention')['touches'],[])
 def test_demarrage_retarde(self):self.succes('retard')
 def test_enregistrement_retarde(self):self.succes('enregistrement-retarde')
 def test_invite_retardee(self):self.succes('invite-retardee')
 def test_quit_selectionne_refuse(self):
  r,d,_=self.jouer('selection-quit')
  self.assertTrue(r.returncode!=0 and not d['touches'] and not d['envois'],'Quit sélectionné validé')
 def test_mission_restee_dans_saisie(self):
  r,d,_=self.jouer('saisie')
  self.assertTrue(r.returncode!=0 and 'mission confiée' not in r.stdout,'saisie annoncée reçue')
 def test_reessai_unique(self):self.succes('reessai',2)
 def test_echo_idle_confirme_reception(self):
  r,d,_=self.jouer('echo-idle')
  self.assertEqual(d['envois'],1,'mission déjà visible renvoyée')
  self.assertTrue(r.returncode==0,'message visible non reconnu')
 def test_echo_tardif_avant_reessai(self):
  r,d,_=self.jouer('echo-tardif')
  self.assertEqual(d['envois'],1,'réception tardive dupliquée')
  self.assertTrue(r.returncode==0,'écho tardif ignoré')
 def test_working_au_second_tour(self):self.succes('working-tardif')
 def test_hooks_ne_sont_pas_le_dialogue_de_confiance(self):
  for scenario in ('hooks-option','hooks-question-citee'):
   with self.subTest(scenario=scenario):
    r,d,_=self.jouer(scenario)
    self.assertEqual(d['touches'],[],'dialogue de hooks validé')
    self.assertEqual(d['envois'],0,'mission envoyée dans un dialogue de hooks')
    self.assertTrue(r.returncode!=0,'écran inconnu annoncé prêt')
 def test_deux_pertes_erreur_claire(self):
  r,d,_=self.jouer('perdu')
  self.assertTrue(r.returncode!=0 and 'réception' in r.stderr and 'mission confiée' not in r.stdout,'perte annoncée comme succès')
  self.assertEqual(d['envois'],2,'nombre de tentatives incorrect')
 def test_refus_api_sans_echo(self):
  r,d,_=self.jouer('refus')
  self.assertTrue(r.returncode!=0 and 'mission confiée' not in r.stdout,'refus ignoré')
  self.assertEqual(d['envois'],2,'refus sans réessai borné')
  self.assertTrue('Nouvelle mission' not in r.stdout+r.stderr,'erreur privée affichée')
 def test_aucun_envoi_sur_ecran_inconnu_ou_agent_absent(self):
  for scenario in ('inconnu','jamais','absent','lecture','ambigu','dialogue-bloque'):
   with self.subTest(scenario=scenario):
    r,d,_=self.jouer(scenario)
    self.assertTrue(r.returncode!=0 and 'mission confiée' not in r.stdout,'démarrage non vérifié')
    self.assertEqual(d['envois'],0,'envoi avant invite prête')
    if scenario=='ambigu':self.assertEqual(d['touches'],[],'choix ambigu accepté')
 def test_question_reapparue(self):
  r,d,_=self.jouer('retour-question')
  self.assertTrue(r.returncode!=0 and d['envois']==2,'question réapparue ignorée')
 def test_claude_inchange(self):
  r,d,_=self.jouer('dialogue','claude')
  self.assertTrue(r.returncode==0 and d['envois']==1 and not d['touches'] and not d['lectures'],'chemin Claude changé')
 def test_codex_ouvert_inchange(self):
  r,d,_=self.jouer('dialogue',strict=False)
  self.assertTrue(r.returncode==0 and d['envois']==1 and not d['touches'] and not d['lectures'],'mur ouvert changé')

class ReceptionEnMemoire(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  arbre=ast.parse((SRC/'bin/moteurs/codex.py').read_text())   # forme d'accès (lot 2)
  fn=next(n for n in arbre.body if isinstance(n,ast.FunctionDef) and n.name=='mission_codex_recue')
  env={'re':re}
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'reception-en-memoire','exec'),env)
  cls.recue=staticmethod(env['mission_codex_recue'])
 def test_texte_dans_saisie_non_soumis(self):
  message='contenupriveessai'
  for saisie in ('› '+message+'\n? for shortcuts',
                 '› Ask Codex…\n  '+message+'\n? for shortcuts',
                 'Historique vide\n❯ '+message+'\n? for shortcuts'):
   self.assertFalse(self.recue(message,saisie,'idle'),'saisie non soumise annoncée reçue')
 def test_texte_soumis_avant_invite(self):
  message='contenupriveessai'
  ecran='› '+message+'\nRéponse\n\n› Ask Codex…\n? for shortcuts'
  self.assertTrue(self.recue(message,ecran,'idle'),'message dans historique ignoré')
 def test_texte_sans_frontiere_de_saisie(self):
  message='contenupriveessai'
  self.assertFalse(self.recue(message,message,'idle'),'écho sans frontière de saisie accepté')
 def test_working_reste_une_confirmation(self):
  self.assertTrue(self.recue('contenupriveessai','› Ask Codex…','working'),'working ignoré')

class DialogueReelEnMemoire(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  arbre=ast.parse((SRC/'bin/moteurs/codex.py').read_text())   # forme d'accès (lot 2)
  noeuds=[n for n in arbre.body if (isinstance(n,ast.FunctionDef) and n.name=='dialogue_confiance_codex') or
          (isinstance(n,ast.Assign) and any(isinstance(v,ast.Name) and v.id in {'CODEX_OPTION_RESTREINTE','CODEX_QUESTION_CONFIANCE','CODEX_OPTION_CONFIANCE','CODEX_OPTION_QUITTER','CODEX_TITRE_CONFIANCE','CODEX_VALIDATION_RESTREINTE'} for v in n.targets))]
  env={'re':re}
  exec(compile(ast.Module(body=noeuds,type_ignores=[]),'dialogue-en-memoire','exec'),env)
  cls.dialogue=staticmethod(env.get('dialogue_confiance_codex',lambda t:False))
  cls.ecran=(SRC/'tests/fixtures/codex-confiance-0.163.0.txt').read_text()
 def test_capture_reelle_fournie(self):self.assertTrue(self.dialogue(self.ecran),'capture réelle non reconnue')
 def test_banniere_avant_capture(self):self.assertTrue(self.dialogue('Codex 0.163.0\n\n'+self.ecran),'bannière rejetée')
 def test_chaque_ligne_obligatoire(self):
  for ligne in ('  Folder access','› 1. Open restricted','  2. Quit','  enter continue · esc quit'):
   with self.subTest(ligne_absente=ligne):
    self.assertFalse(self.dialogue(self.ecran.replace(ligne+'\n','')),'dialogue incomplet accepté')
 def test_ecran_hooks_refuse(self):
  self.assertFalse(self.dialogue(self.ecran.replace('  Folder access','  Hooks need review')),'hooks acceptés')

class SondeCaptureSimulee(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  spec=importlib.util.spec_from_file_location('sonde_confiance',SRC/'tests/sonde-codex-confiance.py')
  cls.sonde=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.sonde)
 def test_session_isolee_fermee_sans_touche(self):
  appels=[]
  def executer(args,**kw):
   appels.append(args)
   return subprocess.CompletedProcess(args,0,'capture' if 'capture-pane' in args else '','')
  resultat=self.sonde.capturer_tmux(['codex','-p','essai'],Path('/dossier/essai'),{},
                                   executer=executer,pause=lambda n:None)
  self.assertTrue(resultat=='capture','capture altérée')
  self.assertTrue(len({a[a.index('-S')+1] for a in appels})==1,'socket non isolée')
  self.assertTrue('kill-session' in appels[-2] and 'kill-server' in appels[-1],'session non fermée')
  self.assertFalse(any('send-keys' in a or 'send-text' in a for a in appels),'touche envoyée par la sonde')
 def test_session_fermee_si_capture_echoue(self):
  appels=[]
  def executer(args,**kw):
   appels.append(args)
   if 'capture-pane' in args:raise subprocess.CalledProcessError(1,args)
   return subprocess.CompletedProcess(args,0,'','')
  with self.assertRaises(subprocess.CalledProcessError):
   self.sonde.capturer_tmux(['codex'],Path('/dossier/essai'),{},executer=executer,pause=lambda n:None)
  self.assertTrue('kill-session' in appels[-2] and 'kill-server' in appels[-1],'échec sans nettoyage')
 def test_fichier_prive_neutralise_exclusif(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   ecran=self.sonde.neutraliser('capture /maison/factice/projet\n', ['/maison/factice/projet'])
   self.assertTrue('/maison/factice' not in ecran,'chemin privé conservé')
   p=self.sonde.ecrire_capture(root/'preuve.txt',ecran,copie=root)
   self.assertTrue(p.stat().st_mode & 0o777==0o600,'capture non privée')
   with self.assertRaises(FileExistsError):self.sonde.ecrire_capture(p,ecran,copie=root)
   with self.assertRaises(ValueError):self.sonde.ecrire_capture(root.parent/'hors-copie',ecran,copie=root)

if __name__=='__main__':unittest.main()
