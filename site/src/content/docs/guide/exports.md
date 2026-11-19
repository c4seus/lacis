---
title: Exporter une enquête
description: "Exporter une enquête entière ou la vue filtrée du graphe dans un fichier JSON qui garde les entités, les liens, les signaux, les notes, les verdicts et la provenance de chaque fait."
---

Un export sort votre enquête de Lacis pour la relire, l'archiver ou la traiter avec d'autres outils. Il ne modifie jamais l'enquête : vous pouvez exporter aussi souvent que vous le voulez.

## Ouvrir la fenêtre d'export

Ouvrez l'enquête, puis choisissez **Fichier › Exporter › JSON…**. La fenêtre « Exporter l'enquête » s'ouvre, avec trois choix :

- **Format** : le format du fichier ;
- **Contenu** : toute l'enquête, ou seulement la vue filtrée ;
- **Destination** : le fichier à écrire.

Le bouton **Exporter** écrit le fichier, et Lacis confirme l'export par une notification qui donne son nom.

## Choisir le contenu

**Toute l'enquête** exporte chaque entité, chaque lien et chaque signal, même ceux que les filtres du graphe cachent.

**La vue filtrée** n'exporte que les entités que le graphe montre, avec les liens dont les deux bouts sont montrés et les signaux de ces entités. Elle suit tous les filtres : types d'entités, entités signalées seulement, tag et verdict. Le choix indique combien d'entités chacun exporte. Sans filtre actif, la vue filtrée est grisée, puisqu'elle serait identique à l'enquête entière.

## Choisir la destination

Lacis propose un fichier au nom de l'enquête dans votre dossier Documents. Modifiez le chemin dans le champ, ou choisissez le fichier avec le bouton **Choisir…**.

Le bouton **Exporter** reste grisé tant que la destination ne peut pas être écrite : un chemin vide, un dossier qui n'existe pas, ou un dossier à la place d'un fichier. Si le fichier existe déjà, Lacis prévient qu'il sera remplacé.

## Le format JSON

L'export JSON est complet et sans perte. Il contient :

- l'enquête : son nom, sa question et sa date de création ;
- les entités : leur type, leur nom, leurs attributs, leurs dates de collecte, leurs tags, leur note, leur verdict avec sa raison, et pour les entreprises leurs annonces BODACC ;
- les liens entre entités, avec leur rôle et leurs dates ;
- les signaux d'alerte, avec leur règle, leur sévérité et leur explication ;
- vos décisions d'homonymie ;
- les réponses des sources, avec leur adresse, leurs paramètres, leur date de collecte et leur empreinte SHA-256.

Chaque entité, chaque lien et chaque annonce cite les réponses dont il vient : la [provenance](/lacis/guide/preuves/) reste vérifiable hors de Lacis.

Le fichier suit un schéma publié, [investigation-1.schema.json](https://c4seus.github.io/lacis/schemas/investigation-1.schema.json), au format JSON Schema. Un outil peut s'en servir pour valider l'export avant de le lire. Le champ `format_version` change si la structure du fichier change.

Un export contient les données personnelles de l'enquête : rangez-le et partagez-le avec les mêmes précautions que l'enquête elle-même. La page [Usage responsable](/lacis/guide/usage-responsable/) rappelle les règles à suivre.
