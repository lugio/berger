# Accès web d'un agent Claude, envoi validé, recherche de traces par le courtier, registre de suivi (spec)

Règle de go : **cas 1** (courtier, accès web, droits d'un agent, un secret : le mot de passe de l'adresse d'envoi) et
**cas 5** (plus d'appels vers des services extérieurs). **Aucune ligne de code avant le go du propriétaire, inscrit sur CE
fichier**, même en local. Cette spec n'est que du texte.

Origine : un agent de vie privée (exemple : `agents/vie-privee`) qui retrouve les données personnelles du propriétaire
exposées sur Internet et en demande l'effacement (RGPD, art. 17). Il est aujourd'hui bloqué : il n'a ni navigateur, ni
envoi de mail. Le besoin est générique : tout agent Claude qui doit remplir un formulaire web ou écrire à une adresse
déclarée, sous validation.

## Constat (mesuré sur `main`)

- **L'accès web encadré existe** (`courtier/_web.py`, spec `docs/plans/archive/2026-10-18-retro-web-spec.md`) :
  - un domaine à la fois, ouvert par une validation du propriétaire (2 h par défaut, 24 h au plus) ;
  - GET et HEAD seulement ; POST seulement si la validation le dit (`post_autorise`, `_web.py:605`) ;
  - chaque requête journalisée ; pas d'autre site, pas de redirection ailleurs, pas d'adresse privée ;
  - « session prêtée » : `berger web connecter <domaine>` ouvre chez le propriétaire un Chromium visible (connexion,
    double authentification) ; l'agent ne voit jamais ce qui est tapé.
- **Le navigateur pilotable n'est branché que pour un agent** (serveur MCP déclaré `web`, `courtier/_mcp.py`, voie B) :
  rien ne permet de le donner à un autre agent Claude par sa configuration.
- **`CHEMINS_BLOQUES`** (`_web.py:22`) refuse tout chemin contenant `delete`, même en POST validé : la plupart des
  formulaires d'effacement (« /privacy/delete-request ») sont donc refusés.
- **Aucun envoi de mail** n'existe pour un agent.

## Comportement prévu

**a. Navigateur pour un agent Claude.** Le serveur MCP `web` se déclare pour n'importe quel agent strict
(`mcp = web` de son `agent.conf`), avec les mêmes murs : enveloppe du courtier, réseau coupé hors du proxy, un domaine
ouvert à la fois, journal. Rien ne change pour l'agent qui l'a déjà.

**b. Chemins d'effacement en POST validé.** `delete` reste bloqué en GET et HEAD. Il est permis **seulement** en POST, et
seulement quand la validation du domaine autorise le POST. `logout`, `export`, `settings` et `payment` restent bloqués
dans tous les cas.

**c. Registre de suivi et panneaux.** Un fichier `suivi/registre.csv` dans le dossier de l'agent (écrit par lui), lu
par trois panneaux Herdr de son espace, onglet « Suivi » :
- **Traces trouvées** : site · ce qui est exposé · date de découverte ;
- **Demandes** : site · état (à rédiger, ⚠ go attendu, envoyée le, réponse, relance à J+30, plainte préparée) ; un délai
  dépassé en rouge ; « ✋ CAPTCHA » quand le propriétaire doit intervenir ;
- **Accès web** : domaine ouvert, durée restante, requêtes refusées.
Les panneaux sont des vues en lecture seule : une ligne illisible est signalée, jamais exécutée.

**d. Envoi de mail à une adresse déclarée.** Un verbe d'écriture du courtier (`mail envoyer`) envoie un texte à une
adresse qui figure sur la **liste validée** (ci-dessous), depuis une adresse d'expédition dédiée à l'agent. Le mot de passe
est dans le coffre (`<agent>.mail_password`), lu par le courtier seul, jamais montré à l'agent. Texte seul, sans pièce
jointe ; débit borné ; chaque envoi journalisé (destinataire, objet, taille, jamais le corps dans les journaux généraux).

**e. Recherche de traces sans navigateur, par le courtier.** Un outil du courtier de type `commandes` : des commandes
**fixées** dans sa définition, jouées dans le bac à sable du courtier, depuis une **version figée installée** (empreinte
vérifiée à l'installation ; jamais `npx`, `pipx run` ni téléchargement à la volée).
- **Maigret** (`github.com/soxoj/maigret`) : un pseudo cherché sur des milliers de sites, en lecture. Licence annoncée
  MIT — *à vérifier* sur la version figée.
- **user-scanner** (`github.com/kaifcodec/user-scanner`) : sur quels sites une adresse a un compte, par la fonction
  « mot de passe oublié ». **À évaluer AVANT tout code** : maintenance, licence (*à vérifier*), et surtout ce qu'il envoie
  aux sites. S'il déclenche une vraie demande de réinitialisation (un mail reçu par le titulaire, une action sur son
  compte), il est **refusé**, ou seuls ses modules passifs sont permis, nommés un par un dans la définition de l'outil.
- **Arguments** : uniquement les pseudos et adresses de `identite.md` de l'agent (lus par le courtier, fichier 600) ; tout
  autre argument est refusé. Le réseau n'est ouvert que pour ces lectures, le temps de la commande, avec un délai borné.
- **Résultats** dans `suivi/` de l'agent ; jamais dans les journaux généraux (`appels.log` garde le verbe, la durée et le
  nombre de résultats, pas les valeurs).

**f. Modèles de lettres.** Les demandes partent des « courriers pour agir » de la CNIL (`cnil.fr`) : effacement (art. 17)
et opposition (art. 21). Une copie datée, avec sa source, dans le dossier de l'agent ; l'agent n'ajoute que les champs
du site. Conditions de réutilisation des textes de la CNIL : *à vérifier* avant de les copier dans le dépôt (sinon le
dépôt ne garde que le lien et la structure).

**g. Adresses des DPO.** La base d'entreprises de datarequests.org (association Datenanfragen.de e.V., existe en
français) : une copie locale **datée**, consultée par l'agent, mise à jour par une installation (jamais à la volée).
Licence des données annoncée libre — *à vérifier* (laquelle, et ses conditions d'attribution). Une adresse trouvée dans
cette base n'est **jamais** une autorisation d'envoi : seul compte la liste validée de la semaine.

**Autonomie dans une liste validée.** Chaque semaine, l'agent présente la liste nommée des sites à saisir ou à relancer
(site, URL, adresse ou formulaire, texte de la demande). **Un seul go du propriétaire sur CETTE liste** autorise les envois
(POST et mails) vers ces sites-là seulement, pendant sa durée. Un site hors liste attend la liste suivante. C'est une
exception à « tout envoi : le propriétaire, à chaque fois », valable pour l'agent qui la déclare, et inscrite par le go
sur cette spec ; `commun/REGLES.md` (« Qui valide quoi ») gagne la ligne correspondante.

**CAPTCHA.** L'agent ne les résout pas et ne les contourne pas. À la place : un mail à l'adresse vie privée du site
(l'art. 17 n'impose pas le formulaire) ; sans adresse, « ✋ CAPTCHA » dans le panneau, et le propriétaire le coche dans
la session prêtée.

**Toujours** : seulement les champs exigés par le site ; une pièce d'identité seulement en cas de doute raisonnable
(art. 12.6), masquée, et sur un go du propriétaire pour CE site.

## Refus nommés

POST sans validation qui le permet ; `delete` en GET ou HEAD ; site ou adresse hors de la liste validée ; liste expirée ;
pièce jointe ; débit dépassé ; mot de passe absent du coffre ; un secret dans le texte d'un envoi (bloqué et notifié,
comme partout) ; serveur MCP `web` non déclaré pour l'agent ; argument de recherche absent d'`identite.md` ; outil de
recherche non installé ou d'empreinte différente ; module de user-scanner non permis.

## Tests (rouges d'abord, sans réseau)

- `delete` : refusé en GET, permis en POST validé, refusé en POST non validé ; les autres chemins toujours refusés.
- MCP `web` donné à un second agent par sa configuration ; refusé sans déclaration ; murs inchangés.
- `mail envoyer` : serveur SMTP factice local ; adresse hors liste, liste expirée, pièce jointe, débit, secret dans le
  texte : refusés ; mot de passe jamais dans une sortie ni un journal.
- Panneaux : registre vide, ligne illisible, délai dépassé.
- Recherche : faux Maigret et faux user-scanner locaux ; argument hors `identite.md` refusé ; empreinte changée refusée ;
  résultats dans `suivi/` et absents d'`appels.log` ; délai borné ; module non permis refusé.

## Lots

1. **a + b** (courtier, accès web) — cas 1.
2. **d** (mail, coffre) et la ligne de `REGLES.md` — cas 1 et 5.
3. **c** (registre et panneaux), avec la documentation.
4. **e** (recherche par le courtier) — cas 1 et 5 ; précédé de l'évaluation écrite de user-scanner et des licences
   (Maigret, user-scanner), remise au propriétaire avant le code de ce lot.
5. **f + g** (modèles de lettres, base des DPO) — après la vérification des conditions de réutilisation.
Une demande de fusion par lot. Ensuite, les gestes du propriétaire : créer l'agent, son adresse d'expédition et sa clé dans
le coffre, ouvrir son espace.
