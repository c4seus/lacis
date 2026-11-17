---
title: Confidentialité du site
description: "Ce que mesure le site de Lacis, sans cookie ni donnée personnelle, ce qu'il garde dans votre navigateur, où vont les statistiques et comment bloquer la mesure."
---

Ce site présente Lacis et son guide. Il n'affiche aucune publicité, ne dépose aucun cookie et ne vous suit pas d'un site à l'autre. Pour savoir combien de personnes le lisent, quelles pages servent et d'où viennent les lecteurs, il compte ses visites avec [GoatCounter](https://www.goatcounter.com/), un outil libre de mesure d'audience.

Cette page concerne le site. Le logiciel Lacis, lui, n'envoie aucune statistique : la page [Vos données](/lacis/guide/donnees/) dit tout ce qu'il envoie sur le réseau.

## Ce qui est compté

À chaque page que vous ouvrez, un petit script envoie à GoatCounter :

- l'adresse de la page ;
- l'adresse du site d'où vous venez, si votre navigateur la transmet ;
- le nom et la version de votre navigateur et de votre système, déduits de l'en-tête `User-Agent` ;
- la taille de votre écran ;
- votre pays, déduit de votre adresse IP.

GoatCounter en tire des statistiques agrégées : le nombre de pages vues et de visites par jour, par page, par site d'origine, par navigateur, par taille d'écran et par pays. Il ne garde pas de trace individuelle de chaque visite.

Pour compter une visite sans la compter deux fois, GoatCounter calcule une empreinte de votre adresse IP et de votre navigateur, mêlée à un nombre tiré au hasard. Cette empreinte reste en mémoire 8 heures au plus et n'est jamais écrite sur disque. Les [explications de GoatCounter](https://www.goatcounter.com/help/sessions) détaillent ce calcul.

## Ce qui n'est pas compté

- Votre adresse IP et l'en-tête `User-Agent` complet ne sont pas conservés.
- Aucun identifiant ne vous suit d'une page à l'autre, ni d'un site à l'autre.
- Aucune donnée n'est partagée, revendue ou utilisée pour de la publicité.
- La recherche du site fonctionne dans votre navigateur : ce que vous y tapez n'est envoyé nulle part.

La mesure ne sert qu'à l'auteur du site, pour savoir si le site et son guide sont utiles. Elle ne figure que dans la version publiée : un aperçu local du site ne charge pas le script.

## Ce que le site garde dans votre navigateur

La mesure d'audience n'écrit rien dans votre navigateur. Le site, lui, retient deux préférences pour son affichage :

- le thème choisi, clair, sombre ou automatique, dans le stockage local, sous la clé `starlight-theme` ;
- les groupes ouverts du menu de gauche et sa position, dans le stockage de session, sous la clé `sl-sidebar-state`. Le navigateur l'efface à la fermeture de l'onglet.

Ces préférences ne quittent jamais votre navigateur. Vous pouvez les effacer avec les données du site, dans les réglages de votre navigateur.

## Où vont les statistiques

Les statistiques sont stockées par le service GoatCounter.com et ne sont visibles que par l'auteur du site. La [politique de confidentialité de GoatCounter](https://www.goatcounter.com/privacy) décrit leur traitement.

Le site est hébergé par GitHub Pages. Comme tout hébergeur, GitHub reçoit les requêtes de votre navigateur et [journalise l'adresse IP des visiteurs pour la sécurité de son service](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages#data-collection), que vous ayez un compte GitHub ou non. L'auteur du site n'a pas accès à ces journaux.

## Bloquer la mesure

Vous pouvez refuser la mesure, sans que le site perde quoi que ce soit :

- un bloqueur de contenu peut bloquer les adresses `gc.zgo.at`, d'où vient le script, et `goatcounter.com`, où partent les visites ;
- vous pouvez aussi désactiver JavaScript pour ce site : les pages restent lisibles, seules la recherche et le choix du thème ne fonctionnent plus.

## Le cadre

Cette mesure d'audience suit les conditions que pose la CNIL pour se passer de consentement : elle sert uniquement à mesurer l'audience du site pour son auteur, elle produit des statistiques anonymes, elle ne recoupe ces données avec aucune autre, et son prestataire ne les réutilise pas. C'est pourquoi le site n'affiche pas de bandeau de consentement. La CNIL détaille ces conditions dans ses [solutions pour les outils de mesure d'audience](https://www.cnil.fr/fr/cookies-solutions-pour-les-outils-de-mesure-daudience).

Pour toute question sur cette page, [ouvrez un signalement](https://github.com/c4seus/lacis/issues/new/choose).

Dernière mise à jour : 15 novembre 2026.
