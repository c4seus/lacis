---
title: Feuille de route
description: "Ce que préparent les prochaines versions de Lacis : rapports et exports, paquets dans les dépôts des distributions, recherche des sociétés d'un dirigeant à l'étranger, et pivots depuis le site web d'une arnaque."
---

Cette page décrit ce que les prochaines versions de Lacis vous permettront de faire, dans l'ordre où elles sortiront. Elle ne donne pas de date : une version sort quand elle est prête et testée. Le [journal des modifications](https://github.com/c4seus/lacis/blob/develop/CHANGELOG.md) liste ce que contiennent les versions déjà publiées.

## Lacis 1.0.0 : livrables et distribution

Une enquête produit un livrable, et pas seulement un graphe à l'écran.

- Notez vos constats sur chaque entité : une note, des tags et un verdict, avec sa raison.
- Générez le rapport de l'enquête : la question, la méthode, les constats rangés par verdict, les signaux, vos notes et une annexe de preuves. Prévisualisez-le, puis exportez-le en Markdown ou en PDF.
- Exportez l'enquête vers les outils que vous utilisez déjà : un fichier JSON complet, un coffre Obsidian, Gephi, Maltego, ou un graphe HTML à ouvrir dans un navigateur.
- Installez Lacis et recevez ses mises à jour avec le gestionnaire de paquets de votre distribution : `apt`, `dnf` ou un assistant de l'AUR.

[Le détail de la version 1.0.0](https://github.com/c4seus/lacis/milestone/4)

## Lacis 1.1.0 : ponts vers l'étranger

Découvrez si un dirigeant français a des sociétés hors de France, sans que Lacis devienne un registre international. Les sources étrangères ne sont interrogées que depuis la fiche d'une personne ou d'une entreprise, pour répondre à une question précise.

- Les mandats d'un dirigeant au Royaume-Uni, dans le registre de Companies House, avec une confiance fondée sur son mois de naissance.
- Ses mentions dans les fuites offshore de l'ICIJ, toujours avec une confiance faible.
- Les chaînes de détention des sociétés qui ont un identifiant LEI.

[Le détail de la version 1.1.0](https://github.com/c4seus/lacis/milestone/5)

## Lacis 1.2.0 : pivots web

Partez du site web d'une arnaque et remontez jusqu'aux entreprises et aux personnes qui sont derrière.

- Les informations publiques d'un nom de domaine : son enregistrement et ses serveurs.
- Les domaines liés, révélés par les certificats qui les couvrent ensemble.
- Le SIREN affiché dans les mentions légales d'un site, qui relie le domaine à l'entreprise.

[Le détail de la version 1.2.0](https://github.com/c4seus/lacis/milestone/3)

## Proposer un besoin

Cette feuille de route n'est pas figée : les besoins des personnes qui enquêtent la font évoluer. Avant de proposer une amélioration, cherchez dans les [signalements existants](https://github.com/c4seus/lacis/issues) : si le vôtre y figure, décrivez votre cas dans un commentaire, il aide à fixer les priorités. Sinon, ouvrez une **Feature request**, comme l'explique la page [Contribuer à Lacis](/lacis/guide/contribuer/#signaler-un-problème), en partant du besoin plutôt que de la solution. Un compte GitHub suffit.
