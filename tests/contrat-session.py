#!/usr/bin/env python3
"""Contrats de session : doubles seulement, aucun socket ni navigateur réel."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import _herdr_isole   # Herdr réel hors d'atteinte (tests/_herdr_isole.py)
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
T=Path(__file__).resolve().parent

def charger(n,f):
    spec=importlib.util.spec_from_file_location(n,T/f);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
C=charger('contrat_session','contrat-moteur.py');S=charger('sonde_session','sonde-mcp.py')

class Sonde(unittest.TestCase):
    def test_dom_ne_confond_pas_script_texte_et_attributs(self):
        brut='<body><script>const exemple=\'data-script="true" data-cookie-vide="true"\';</script></body>'
        with patch.object(S.subprocess,'run',return_value=subprocess.CompletedProcess([],0,brut,'')):
            x=S.web(['https://permis.test/'],navigateur=True)['urls']['https://permis.test/']
        self.assertIs(x.get('script'),False);self.assertIs(x.get('cookie_vide'),False)
        dom='<body data-script="true" data-cookie-vide="true"><script></script></body>'
        with patch.object(S.subprocess,'run',return_value=subprocess.CompletedProcess([],0,dom,'')):
            x=S.web(['https://permis.test/'],navigateur=True)['urls']['https://permis.test/']
        self.assertIs(x.get('script'),True);self.assertIs(x.get('cookie_vide'),True)
    def test_lire_ouvre_sans_lire_contenu(self):
        with tempfile.TemporaryDirectory() as d:
            temoin=Path(d)/'temoin';temoin.write_text('SECRET')
            with patch.object(S.Path,'read_text',side_effect=AssertionError('lecture de contenu interdite')):
                r=S.web([],lire=[str(temoin),str(Path(d)/'absent')])
            self.assertEqual(r['lus'],[str(temoin)]);self.assertNotIn('SECRET',json.dumps(r))
    def test_tunnel_methode_statut_interieur_et_setcookie(self):
        class Brut:
            def __init__(self):self.entete=bytearray(b'HTTP/1.1 200 Connection established\r\n\r\n')
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def sendall(self,b):pass
            def recv(self,n):
                if not self.entete:return b''
                b=bytes(self.entete[:n]);del self.entete[:n];return b
        class TLS:
            requete=b'';reste=b'HTTP/1.1 405 Refused\r\nSet-Cookie: temoin=factice\r\n\r\n'
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def sendall(self,b):self.requete=b
            def recv(self,n):b=self.reste;self.reste=b'';return b
        tls=TLS()
        with patch.object(S.socket,'create_connection',return_value=Brut()),patch.object(S.ssl,'create_default_context',return_value=SimpleNamespace(wrap_socket=lambda *a,**kw:tls)):
            r=S.web([],tunnels=[{'hote':'permis.test','sni':'permis.test','methode':'POST'}])
        t=r['tunnels'][0];self.assertEqual(t['statut'],405);self.assertIs(t['set_cookie'],True)
        self.assertTrue(tls.requete.startswith(b'POST / HTTP/1.1\r\n'));self.assertNotIn('SECRET',json.dumps(r))
    def test_pose_fichier_public_et_restauration(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);f=d/'cert.pem';f.write_text('ancien public');p=C.Pose(d/'pose.json')
            p.poser(f,'nouveau public');p.retirer();self.assertEqual(f.read_text(),'ancien public')
            p.poser(f,'nouveau public');f.write_text('public modifié par un tiers');p.retirer()
            self.assertEqual(f.read_text(),'public modifié par un tiers')
            g=d/'spki';p.poser(g,C.MARQUE+' public');g.write_text(C.MARQUE+' modifié par un tiers');p.retirer()
            self.assertEqual(g.read_text(),C.MARQUE+' modifié par un tiers')


    def test_reprise_apres_interruption_ecriture_temporaire(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);f=d/'cert.pem';f.write_text('original intact')
            pose=C.Pose(d/'pose.json');fdopen=C.os.fdopen
            class Interrompre:
                def __init__(self,fd,mode):self.flux=fdopen(fd,mode)
                def __enter__(self):return self
                def __exit__(self,*a):self.flux.close()
                def write(self,texte):
                    self.flux.write(texte[:len(texte)//2]);self.flux.flush()
                    raise KeyboardInterrupt()
            with patch.object(C.os,'fdopen',Interrompre):
                with self.assertRaises(KeyboardInterrupt):pose.poser(f,'nouveau certificat public')
            self.assertEqual(f.read_text(),'original intact')
            journal=json.loads((d/'pose.json').read_text());temp=Path(journal[0]['temp'])
            self.assertTrue(temp.exists());self.assertNotEqual(temp.read_text(),'nouveau certificat public')
            self.assertEqual(C.Pose(d/'pose.json').reprendre(),1)
            self.assertEqual(f.read_text(),'original intact');self.assertFalse(temp.exists())
            self.assertEqual(list(d.glob('*.avant-contrat*')),[])
    def test_reprise_apres_deux_poses_sans_finally(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);f=d/'spki';f.write_text('original')
            pose=C.Pose(d/'pose.json');pose.poser(f,'contrat-7');pose.poser(f,'contrat-10')
            self.assertEqual(C.Pose(d/'pose.json').reprendre(),2)
            self.assertEqual(f.read_text(),'original');self.assertEqual(list(d.glob('*.avant-contrat*')),[])
    def test_depilement_partiel_garde_poses_precedentes(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);f=d/'cert.pem';f.write_text('original')
            pose=C.Pose(d/'pose.json');pose.poser(f,'contrat-7');point=len(pose.faits)
            pose.poser(f,'contrat-10');pose.retirer(depuis=point)
            self.assertEqual(f.read_text(),'contrat-7');self.assertEqual(len(pose.faits),point)
            self.assertEqual(json.loads((d/'pose.json').read_text()),pose.faits)
            pose.retirer();self.assertEqual(f.read_text(),'original');self.assertEqual(list(d.glob('*.avant-contrat*')),[])

class Verdicts(unittest.TestCase):
    def mesure(self, mode='ok'):
        refs={};verdicts=[];appels=[]
        sessions=charger('sessions_factice','../courtier/_web_session.py')
        def dossier(s,a):return Path(s)/(a+'-web')
        def chemin(s,a):return dossier(s,a)/'proxy.sock'
        class Site:
            port=12345;certificat_pem=b'certificat public';n=0
            def __init__(self,marque,attendu):self.marque=marque;self.attendu=attendu;self.requetes=[];self.ferme=False;refs['site']=self
            def fermer(self):self.ferme=True
        class Proxy:
            empreinte='SPKI-factice';certificat_pem=b'certificat public proxy'
            def __init__(self,noms,journal,**kw):self.journal=journal;self.ouvrir=kw['ouvrir'];self.stop=False
            def arreter(self):self.stop=True
        class Acces:
            def __init__(self,sockets,etats,journal,journal_agent,*,fabrique,sessions):
                self.sockets,self.etats,self.journal,self.ja,self.fabrique,self.sessions=sockets,etats,journal,journal_agent,fabrique,sessions
                self.ouverts={};self.nettoye=False;refs['acces']=self
            def ouvert(self,a):return self.ouverts.get(a)
            def chemin(self,a):return chemin(self.sockets,a)
            def ouvrir(self,a,noms,secondes,session=False):
                p=self.fabrique(noms,lambda m,h,ok,d:self.journal(a,'web:'+h,m,[h],ok,d))
                self.ouverts[a]={'proxy':p,'fin_ts':1000};self.agent=a;refs['proxy']=p
                self.etats.mkdir(parents=True);(self.etats/(a+'.json')).write_text('{}')
                dossier(self.sockets,a).mkdir(parents=True,exist_ok=True);self.chemin(a).touch()
                (dossier(self.sockets,a)/'spki').write_text(p.empreinte+'\n')
            def fermer(self,a,raison):
                if a not in self.ouverts:return
                self.ouverts.pop(a)['proxy'].arreter()
                if mode!='cle_physique_restante':self.sessions.effacer('permis.test')
                self.chemin(a).unlink(missing_ok=True);(self.etats/(a+'.json')).unlink(missing_ok=True)
                (dossier(self.sockets,a)/'spki').unlink(missing_ok=True)
                self.journal(a,'web:permis.test','fermer',[],True,raison);self.ja(a,'révoque ta session')
            def tour(self):
                if mode!='echeance_ignoree':self.fermer(self.agent,'échéance')
            def nettoyer(self):
                self.nettoye=True
        class Relais:
            def __init__(self,a):self.a=a;self.ferme=False;refs['relais']=self
            def fermer(self):self.ferme=True
            def web(self,**kw):
                appels.append(kw)
                if mode=='exception':raise RuntimeError('mesure cassée')
                acc,site=refs['acces'],refs['site'];p=acc.ouvert(self.a)['proxy']
                def joindre(methode):
                    p.ouvrir(('8.8.8.8',443));site.n+=1
                    cookie=acc.sessions.cookie('permis.test',agent=self.a)==site.attendu and mode!='cookie_absent'
                    site.requetes.append({'methode':methode,'cookie':cookie})
                urls={}
                for u in kw.get('urls',[]):
                    if u.startswith('https://'):
                        joindre('GET');p.journal('GET','permis.test',True,'factice')
                        urls[u]=dict(execute=mode!='navigateur_panne',marque=True,pre=False,script=mode!='script_absent',cookie_vide=mode!='cookie_dom')
                    elif 'coffre-factice' in u:
                        urls[u]=dict(execute=True,marque=mode=='coffre_lisible',pre=mode=='coffre_lisible')
                    else:urls[u]=dict(execute=True,marque=mode!='temoin_absent',pre=True)
                lus=[x for x in kw.get('lire',[]) if ('coffre-factice' not in x or mode=='open_coffre') and mode!='temoin_absent']
                tunnels=[]
                for t in kw.get('tunnels',[]):
                    m=t.get('methode','GET');get=m=='GET'
                    if get or mode=='post_amont':joindre(m)
                    if mode!='journal_absent' or get:p.journal(m,'permis.test',get,'factice')
                    r=dict(code=200,hello=True,statut=200 if get else 405,marque=get,set_cookie=mode=='set_cookie')
                    if get and mode=='get_panne':r.update(hello=False,statut=0,marque=False)
                    if not get and mode=='mauvais_statut':r['statut']=502
                    if not get and mode=='tls_erreur':r['erreur']='connexion interrompue'
                    tunnels.append(r)
                return {'urls':urls,'tunnels':tunnels,'lus':lus}
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);(base/'ecriture').mkdir()
            publics=dossier(base/'courtier/mcp','alice');publics.mkdir(parents=True)
            (publics/'spki').write_text('ancien SPKI');(publics/'cert.pem').write_text('ancien certificat')
            pose=C.Pose(base/'pose.json')
            w=SimpleNamespace(Proxy=Proxy,Acces=Acces,dossier_socket=dossier,chemin_socket=chemin)
            with patch.object(C,'B',base),patch.object(C,'charger_web',return_value=w),patch.object(C,'charger_sessions',return_value=sessions), \
                 patch.object(C,'FauxSiteSession',Site),patch.object(C,'Relais',Relais), \
                 patch.object(C.ssl,'create_default_context',return_value=object()),patch.object(C.socket,'create_connection',return_value=object()):
                C.conditions_session_web(lambda ok,msg:verdicts.append((bool(ok),msg)),'alice',{'ecriture':[str(base/'ecriture')]},pose)
            self.assertEqual((publics/'spki').read_text(),'ancien SPKI');self.assertEqual((publics/'cert.pem').read_text(),'ancien certificat')
            self.assertEqual(list((base/'courtier/validations').iterdir()),[])
            self.assertTrue(refs['proxy'].stop);self.assertFalse(chemin(base/'courtier/mcp','alice').exists())
            self.assertTrue(refs['site'].ferme);self.assertTrue(refs['relais'].ferme);self.assertTrue(refs['acces'].nettoye)
            pose.retirer()
        return verdicts,appels
    def test_mesure_complete_sur_doubles(self):
        v,appels=self.mesure();self.assertTrue(v);self.assertTrue(all(ok for ok,_ in v),v)
        methodes=[t['methode'] for a in appels for t in a.get('tunnels',[])]
        self.assertEqual(methodes,['GET','POST','DELETE'])
        self.assertEqual(sum('(11) échéance' in msg for _,msg in v),1)
    def test_temoins_absents_interdisent_tout_verdict_negatif_vert(self):
        for mode in ('navigateur_panne','script_absent','get_panne','temoin_absent','exception'):
            with self.subTest(mode=mode):
                v,_=self.mesure(mode)
                conclusions=[ok for ok,msg in v if msg.startswith(('(10)','(11)'))]
                self.assertTrue(conclusions);self.assertFalse(any(conclusions),v)
    def test_fuites_et_ecriture_amont_refusent_admission(self):
        for mode in ('cookie_absent','cookie_dom','set_cookie','coffre_lisible','open_coffre','post_amont','journal_absent','mauvais_statut','tls_erreur','cle_physique_restante','echeance_ignoree'):
            with self.subTest(mode=mode):
                v,_=self.mesure(mode)
                self.assertFalse(all(ok for ok,_ in v),v)

if __name__=='__main__':unittest.main()
