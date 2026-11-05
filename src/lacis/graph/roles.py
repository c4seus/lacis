from enum import StrEnum

from lacis.storage.comparison_keys import normalise_text


class DirectorRole(StrEnum):
    PRESIDENT = "Président"
    CHIEF_EXECUTIVE = "Directeur général"
    DEPUTY_CHIEF_EXECUTIVE = "Directeur général délégué"
    DIRECTOR = "Directeur"
    MANAGER = "Gérant"
    PARTNER = "Associé"
    BOARD_CHAIR = "Président du conseil d'administration"
    BOARD_MEMBER = "Administrateur"
    MANAGEMENT_BOARD_CHAIR = "Président du directoire"
    MANAGEMENT_BOARD_MEMBER = "Membre du directoire"
    SUPERVISORY_BOARD_CHAIR = "Président du conseil de surveillance"
    SUPERVISORY_BOARD_MEMBER = "Membre du conseil de surveillance"
    STATUTORY_AUDITOR = "Commissaire aux comptes"
    ALTERNATE_AUDITOR = "Commissaire aux comptes suppléant"
    LIQUIDATOR = "Liquidateur"
    PERMANENT_REPRESENTATIVE = "Représentant permanent"
    SOLE_PROPRIETOR = "Entrepreneur individuel"
    OTHER = "Autre fonction"
    UNSPECIFIED = "Fonction non précisée"


MASCULINE_WORDS = {
    "ADMINISTRATRICE": "ADMINISTRATEUR",
    "ASSOCIEE": "ASSOCIE",
    "COGERANT": "GERANT",
    "COGERANTE": "GERANT",
    "COMMERCANTE": "COMMERCANT",
    "DELEGUEE": "DELEGUE",
    "DIRECTRICE": "DIRECTEUR",
    "ENTREPRENEUSE": "ENTREPRENEUR",
    "EXPLOITANTE": "EXPLOITANT",
    "GENERALE": "GENERAL",
    "GERANTE": "GERANT",
    "LIQUIDATRICE": "LIQUIDATEUR",
    "PRESIDENTE": "PRESIDENT",
    "REPRESENTANTE": "REPRESENTANT",
    "SUPPLEANTE": "SUPPLEANT",
}
ROLE_WORDS = (
    ({"PRESIDENT", "CONSEIL", "SURVEILLANCE"}, DirectorRole.SUPERVISORY_BOARD_CHAIR),
    ({"CONSEIL", "SURVEILLANCE"}, DirectorRole.SUPERVISORY_BOARD_MEMBER),
    ({"PRESIDENT", "DIRECTOIRE"}, DirectorRole.MANAGEMENT_BOARD_CHAIR),
    ({"DIRECTOIRE"}, DirectorRole.MANAGEMENT_BOARD_MEMBER),
    ({"PRESIDENT", "CONSEIL", "ADMINISTRATION"}, DirectorRole.BOARD_CHAIR),
    ({"ADMINISTRATEUR"}, DirectorRole.BOARD_MEMBER),
    ({"COMMISSAIRE", "COMPTES", "SUPPLEANT"}, DirectorRole.ALTERNATE_AUDITOR),
    ({"COMMISSAIRE", "COMPTES"}, DirectorRole.STATUTORY_AUDITOR),
    ({"REPRESENTANT", "PERMANENT"}, DirectorRole.PERMANENT_REPRESENTATIVE),
    ({"DIRECTEUR", "GENERAL", "DELEGUE"}, DirectorRole.DEPUTY_CHIEF_EXECUTIVE),
    ({"DIRECTEUR", "GENERAL"}, DirectorRole.CHIEF_EXECUTIVE),
    ({"LIQUIDATEUR"}, DirectorRole.LIQUIDATOR),
    ({"GERANT"}, DirectorRole.MANAGER),
    ({"ASSOCIE"}, DirectorRole.PARTNER),
    ({"PRESIDENT"}, DirectorRole.PRESIDENT),
    ({"DIRECTEUR"}, DirectorRole.DIRECTOR),
    ({"ENTREPRENEUR"}, DirectorRole.SOLE_PROPRIETOR),
    ({"EXPLOITANT"}, DirectorRole.SOLE_PROPRIETOR),
    ({"COMMERCANT"}, DirectorRole.SOLE_PROPRIETOR),
)


def director_role(quality: str | None) -> DirectorRole:
    words = {MASCULINE_WORDS.get(word, word) for word in normalise_text(quality or "").split()}
    if not words:
        return DirectorRole.UNSPECIFIED
    for required_words, role in ROLE_WORDS:
        if required_words <= words:
            return role
    return DirectorRole.OTHER
