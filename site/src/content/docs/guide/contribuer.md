---
title: Contribuer à Lacis
description: "Signaler un problème, proposer une amélioration, corriger le guide ou le code de Lacis, et signaler une faille de sécurité en privé."
---

Lacis est un logiciel libre, publié sous la licence [GNU GPL v3](https://github.com/c4seus/lacis/blob/develop/LICENSE) et développé ouvertement sur [GitHub](https://github.com/c4seus/lacis). Chacun peut signaler un problème, proposer une amélioration ou contribuer au code et à ce guide.

:::note
L'interface de Lacis et ce site sont en français, parce que Lacis est fait pour les données des entreprises françaises. Le reste du projet est en anglais : le code, les signalements, les propositions et les documents de contribution. Écrivez vos signalements en anglais si vous le pouvez ; un outil de traduction fait très bien l'affaire.
:::

## Signaler un problème

**Aide › Signaler un problème…**, dans Lacis, ouvre la page des [nouveaux signalements](https://github.com/c4seus/lacis/issues/new/choose). Choisissez :

- **Bug report** pour un problème : la page [Dépannage](/lacis/guide/depannage/#signaler-un-bug) dit quoi y mettre, et comment retirer les données personnelles du journal ;
- **Feature request** pour proposer une amélioration ou une nouvelle fonctionnalité, en partant du besoin plutôt que de la solution.

Avant d'ouvrir un signalement, cherchez dans les [signalements existants](https://github.com/c4seus/lacis/issues) : le vôtre y figure peut-être déjà. Un signalement est public, comme tout ce qui est écrit sur GitHub : n'y mettez jamais de données réelles d'une enquête.

## Signaler une faille de sécurité

Une faille de sécurité ne se signale pas publiquement. Utilisez le [signalement privé de GitHub](https://github.com/c4seus/lacis/security/advisories/new), comme l'explique la [politique de sécurité](https://github.com/c4seus/lacis/blob/develop/SECURITY.md), en anglais. Elle précise ce qui relève de la sécurité de Lacis, comme l'altération des preuves ou une fuite de données, et le délai de réponse.

## Corriger ce guide

Chaque page de ce guide se termine par le lien **Modifier cette page**, qui ouvre sa source sur GitHub. Une faute, une explication peu claire, une capture qui ne correspond plus à l'interface : votre correction est la bienvenue. Les pages sont écrites en français.

## Contribuer au code

Le [guide de contribution](https://github.com/c4seus/lacis/blob/develop/CONTRIBUTING.md), en anglais, décrit l'installation de l'environnement de développement, les branches, la convention des commits, le style du code et les tests que chaque proposition doit inclure. Toute modification part d'un signalement : choisissez-en un, ou ouvrez-le, avant d'écrire du code, pour vous accorder d'abord sur son périmètre.

Pour suivre le projet :

- le [journal des modifications](https://github.com/c4seus/lacis/blob/develop/CHANGELOG.md) liste les changements de chaque version ;
- les [jalons](https://github.com/c4seus/lacis/milestones) regroupent ce que préparent les prochaines versions ;
- les [décisions d'architecture](https://github.com/c4seus/lacis/blob/develop/docs/adr/README.md) expliquent les choix techniques.
