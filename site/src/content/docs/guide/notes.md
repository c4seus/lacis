---
title: Noter vos constats
description: "Donner un verdict sur une entité, écrire une note en Markdown, regrouper les entités avec des tags, et filtrer le graphe, la colonne « À examiner » et l'onglet Entités par tag ou par verdict."
---

Les notes gardent ce que vous avez compris d'une entité : pourquoi elle compte pour votre question, ce qu'il reste à vérifier, ce que vous en concluez. Elles restent à part des faits collectés : écrire ou effacer une note ne change jamais une entité, un lien ou un signal.

## Donner un verdict

Le verdict dit où vous en êtes sur une entité. Il en existe quatre :

- **À vérifier** : l'entité mérite un examen que vous n'avez pas encore fait ;
- **Suspect** : ce que vous avez vu vous inquiète ;
- **Écarté** : l'entité est hors de cause pour votre question ;
- **Confirmé** : vos vérifications confirment ce que vous soupçonniez.

Dans la fiche, la section « Verdict » suit les signaux d'alerte. Choisissez le verdict dans la liste, et ajoutez si vous le voulez une raison dans le champ voisin : elle est enregistrée quand vous quittez le champ. Lacis indique la date du verdict. Pour le retirer, choisissez « Aucun verdict ».

Un verdict reste votre avis : il ne masque ni ne change aucun fait collecté, aucun lien et aucun signal. Une entité écartée reste dans le graphe, avec ses signaux.

Dans le graphe, une pastille en haut à gauche de l'entité montre son verdict : « ? » à vérifier, « ! » suspect, « ✕ » écarté, « ✓ » confirmé. La légende les rappelle, et la description de l'entité dit « verdict : suspect ». L'onglet **Entités** a une colonne « Verdict », triable.

## Écrire une note

Sélectionnez une entité : sa fiche s'ouvre dans le panneau de droite. La section « Notes » contient un champ de texte, sous les signaux d'alerte.

Écrivez directement dans le champ. Lacis enregistre la note seul, une fraction de seconde après votre dernière frappe, et aussi quand vous quittez le champ, changez d'entité ou fermez l'enquête. Il n'y a pas de bouton pour enregistrer. Sous le champ, Lacis indique la date de création de la note et celle de sa dernière modification.

Pour effacer une note, videz le champ : l'entité n'a plus de note.

Chaque entité a une seule note. Une note appartient à l'enquête : elle reste quand vous fermez Lacis, et elle disparaît avec l'enquête si vous la supprimez.

## Mettre en forme avec Markdown

La note accepte le [Markdown](https://commonmark.org/help/) : `**gras**`, `*italique*`, les listes qui commencent par `-`, les titres qui commencent par `#`. Le bouton **Aperçu** affiche la note mise en forme, et le bouton **Modifier** revient au texte.

## Retrouver les entités annotées

Une entité qui a une note porte une petite feuille en haut à droite de sa forme dans le graphe. La légende du graphe la rappelle, et la description de l'entité, lue par les lecteurs d'écran ou au survol, se termine par « avec une note ».

Dans l'onglet **Entités**, la colonne « Note » indique « Oui » pour chaque entité annotée.

## Regrouper avec des tags

Les tags regroupent des entités dispersées dans le graphe : « à recontacter », « client », « réseau Dupont ». Une entité peut en porter autant que vous voulez.

Dans la fiche, la section « Tags » suit les notes. Écrivez un tag dans le champ « Ajouter un tag », puis appuyez sur <kbd>Entrée</kbd>. Pendant la frappe, Lacis propose les tags déjà utilisés dans l'enquête. Chaque tag de l'entité s'affiche au-dessus du champ avec une croix : cliquez dessus pour retirer le tag de cette entité.

Lacis ignore la casse et les espaces en trop : « Client », « CLIENT » et « client » suivi d'un espace sont le même tag. Il garde l'écriture du premier emploi, et la réutilise pour les entités suivantes.

## Filtrer par tag ou par verdict

Choisir un tag ou un verdict filtre toute l'enquête à la fois :

- le graphe n'affiche que les entités qui portent ce tag ou ce verdict ;
- la colonne « À examiner » ne garde que les signaux, les homonymes et les pistes qui les concernent ;
- l'onglet **Entités** ne liste qu'elles.

Vous pouvez choisir le tag et le verdict à deux endroits, qui restent accordés : les sous-menus **Tag** et **Verdict** du bouton **Filtres**, au-dessus du graphe, et les listes « Tous les tags » et « Tous les verdicts » de l'onglet **Entités**. Un tag et un verdict se combinent : « client » et « Suspect » ne gardent que les clients suspects. Pour tout afficher de nouveau, cliquez sur **Tout afficher** en tête de la colonne « À examiner », ou choisissez **Filtres › Tout afficher**. Si plus aucune entité ne porte le tag choisi, ce filtre disparaît.

## Au clavier

Dans la fiche, <kbd>Tab</kbd> atteint la liste du verdict et sa raison, le champ de la note, le bouton **Aperçu**, puis les tags de l'entité et le champ « Ajouter un tag ». Dans le champ, <kbd>Tab</kbd> passe au bouton suivant au lieu d'insérer une tabulation : la note se quitte toujours au clavier.
