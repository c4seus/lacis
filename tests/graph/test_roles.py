import pytest

from lacis.graph.roles import DirectorRole, director_role


@pytest.mark.parametrize(
    ("quality", "role"),
    [
        ("Président", DirectorRole.PRESIDENT),
        ("Présidente", DirectorRole.PRESIDENT),
        ("PRESIDENT DE SAS", DirectorRole.PRESIDENT),
        ("Directeur général", DirectorRole.CHIEF_EXECUTIVE),
        ("Directrice Générale", DirectorRole.CHIEF_EXECUTIVE),
        ("Directeur Général Délégué", DirectorRole.DEPUTY_CHIEF_EXECUTIVE),
        ("Directrice générale déléguée", DirectorRole.DEPUTY_CHIEF_EXECUTIVE),
        ("Directeur", DirectorRole.DIRECTOR),
        ("Gérant", DirectorRole.MANAGER),
        ("Gérante", DirectorRole.MANAGER),
        ("Co-gérant", DirectorRole.MANAGER),
        ("Cogérante", DirectorRole.MANAGER),
        ("Associé", DirectorRole.PARTNER),
        ("Associée indéfiniment responsable", DirectorRole.PARTNER),
        ("Associé gérant", DirectorRole.MANAGER),
        ("Président du conseil d'administration", DirectorRole.BOARD_CHAIR),
        ("Administrateur", DirectorRole.BOARD_MEMBER),
        ("Administratrice", DirectorRole.BOARD_MEMBER),
        ("Président du directoire", DirectorRole.MANAGEMENT_BOARD_CHAIR),
        ("Membre du directoire", DirectorRole.MANAGEMENT_BOARD_MEMBER),
        ("Président du conseil de surveillance", DirectorRole.SUPERVISORY_BOARD_CHAIR),
        ("Membre du conseil de surveillance", DirectorRole.SUPERVISORY_BOARD_MEMBER),
        ("Commissaire aux comptes titulaire", DirectorRole.STATUTORY_AUDITOR),
        ("Commissaire aux comptes suppléant", DirectorRole.ALTERNATE_AUDITOR),
        ("Liquidateur amiable", DirectorRole.LIQUIDATOR),
        ("Administrateur judiciaire", DirectorRole.COURT_ADMINISTRATOR),
        ("Administratrice judiciaire", DirectorRole.COURT_ADMINISTRATOR),
        ("Mandataire judiciaire", DirectorRole.COURT_REPRESENTATIVE),
        ("Liquidateur judiciaire", DirectorRole.COURT_LIQUIDATOR),
        ("Représentant permanent", DirectorRole.PERMANENT_REPRESENTATIVE),
        ("Entrepreneur", DirectorRole.SOLE_PROPRIETOR),
        ("Exploitante", DirectorRole.SOLE_PROPRIETOR),
        ("Commerçant", DirectorRole.SOLE_PROPRIETOR),
        ("Mandataire ad hoc", DirectorRole.OTHER),
        ("", DirectorRole.UNSPECIFIED),
        ("  ", DirectorRole.UNSPECIFIED),
        (None, DirectorRole.UNSPECIFIED),
    ],
)
def test_a_role_is_mapped_to_a_fixed_french_label(quality: str | None, role: DirectorRole) -> None:
    assert director_role(quality) is role


def test_the_labels_are_french_and_distinct() -> None:
    labels = [role.value for role in DirectorRole]
    assert len(set(labels)) == len(labels)
    assert DirectorRole.ALTERNATE_AUDITOR.value == "Commissaire aux comptes suppléant"
