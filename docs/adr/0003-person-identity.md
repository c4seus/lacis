# 0003. A person is a director of one company, and only the investigator joins people

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

The national company register gives no identifier to the people who run a company. For each natural person among the directors of a company, it gives a last name, first names, a month of birth, a nationality and a role. The month of birth is often missing, notably for sole proprietors, and the register lists a person again for each company they run, with no link between those entries.

Lacis 0.1.0 gives each person an identifier made of their last name, their first names and their month of birth (`person_identifier`). Every entry of the register that shares them becomes the same entity:

- two different people with the same name, born the same month, are one entity, without any proposal or decision;
- without a month of birth, the name alone makes the identifier, so every director with that name becomes one entity.

The signals then count the mandates of these people together. A phoenix scheme, serial short-lived companies or a burst of creations can be flagged on a person who does not exist. The user guide promises the opposite: Lacis never joins two people without a decision of the investigator, and homonym proposals exist for that purpose.

The homonym proposals, their confidence and the decisions « Même personne » and « Personne différente » already exist (0.1.0). The signal rules already count people through these decisions, and their setting `include_probable` lets them also count certain and probable proposals. Only the identifier bypasses them.

## Options

| Option | Two people with the same name and month | Same name without month | Drawbacks |
|---|---|---|---|
| Add the company to the identifier only when the month is missing | Still one entity | Separate entities | Common names born the same month, such as a « Jean MARTIN » of March 1975, stay silently merged |
| **One person entity per company, joined only by decisions** | Separate entities, proposed as homonyms | Separate entities, proposed as homonyms | More nodes in the graph and more proposals to review |
| Keep the merged entities in the graph, and split them only in the signals | One node, counted as two people | One node, counted as two people | The graph and the signals tell different stories, and the investigator cannot see or undo the merge |
| Use an identifier of persons from another source | Separate entities, joined by the identifier | Separate entities, joined by the identifier | No open source used by Lacis offers one: it would need another service, with an account and credentials |

## Decision

**A person entity stands for a natural person as the register lists them among the directors of one company.** Its identifier is made of their last name, their first names, their month of birth, or nothing when it is missing, and the SIREN of that company. A person who holds two roles in the same company is one entity with two mandates. Two entries of one company with the same name and month cannot be told apart, and stay one entity.

**Two person entities are the same person only on a decision of the investigator.** Lacis never joins them on its own, whatever the corroboration:

- every pair of person entities with the same last name, months of birth that agree and first names that agree becomes a homonym proposal, as in 0.1.0. Exact matches, which 0.1.0 merged, are now proposals too;
- the corroborations of the graph, such as a shared company or address, only raise the confidence of a proposal, as in 0.1.0;
- a « Même personne » decision links the two entities, and the signals count them as one person. Decisions chain: three entities joined two by two count as one person;
- the setting `include_probable` of the director rules stays off by default. When the investigator turns it on, the signals also count the certain and probable proposals as one person, as in 0.1.0. The graph never does.

**The expansion of a person searches the register for their name, as in 0.1.0.** Each director of another company who bears that name becomes a person entity of that company, linked to it by a mandate, and proposed as a homonym of the expanded person. Their own expansion would run the same search or a narrower one, so they are marked as expanded when the search read every result.

Directors that are companies keep their SIREN as identifier, and foreign companies their name and country. This record changes neither.

**Existing investigations are migrated when they are opened.** Each person entity becomes one person entity for each company it runs:

- each new entity keeps the attributes of the former one, its expansion date and the sources of its mandate, and receives the mandates of its company;
- a « Même personne » decision between two former entities that each become one new entity is kept, with its date;
- a « Même personne » decision about a former entity that splits into several new entities cannot be attributed: the investigator may have had any of its companies in mind. Lacis does not guess, and drops it. Its new entities come back as homonym proposals, so the investigator decides again, and confirms the merges that 0.1.0 made without asking;
- a « Personne différente » decision about a former entity applies to each of its new entities. In doubt, keeping people apart never makes a signal count two people together;
- the position of a former entity in the graph goes to its first new entity by SIREN, and the layout places the others.

## Consequences

- No signal counts the mandates of two entries of the register together before the investigator decides they are one person, unless they turn on `include_probable`.
- A « Même personne » decision about a person that 0.1.0 had merged across several companies is lost, and must be taken again. The « homonymes confirmés » counter only counts decisions that still hold.
- With the default settings, the director rules need decisions to see a person across several companies: confirming homonyms becomes part of every investigation. The review queue shows the certain proposals first.
- The graph shows one node for each company a person runs, joined by « même personne » links once decided. Grouping them into a single node is left to a later record.
- Proposals grow with the number of mandates of a common name. Deciding several proposals at once is left to a later record.
- The migration is the 15th of the schema. An investigation opened by this version cannot be opened by 0.1.0, which refuses newer files with a clear message.
- The page « Vérifier les homonymes » of the user guide drops its warning about perfect homonyms, and explains that each company of a person appears as a separate person until the investigator decides.
