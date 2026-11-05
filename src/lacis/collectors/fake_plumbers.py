from lacis.collectors.fictional_records import (
    FictionalAddress,
    FictionalCompany,
    FictionalEstablishment,
    FictionalLegalPerson,
    FictionalNaturalPerson,
    FictionalNotice,
    FictionalScenario,
)

FAKE_PLUMBERS_INVESTIGATION_NAME = "faux-plombiers-31"
FAKE_PLUMBERS_QUESTION = "Qui se cache derrière les sociétés de plomberie à cette adresse ?"
TOULOUSE_COURT = "GREFFE DU TRIBUNAL DE COMMERCE DE TOULOUSE"
MARSEILLE_COURT = "GREFFE DU TRIBUNAL DE COMMERCE DE MARSEILLE"

SHARED_ADDRESS = FictionalAddress(
    "12",
    "RUE",
    "DES LILAS",
    "31000",
    "TOULOUSE",
    "31555",
    "Haute-Garonne",
    "76",
    "Occitanie",
    "43.6047",
    "1.4442",
)
HOLDING_ADDRESS = FictionalAddress(
    "5",
    "AVENUE",
    "DU PORT",
    "13002",
    "MARSEILLE",
    "13202",
    "Bouches-du-Rhône",
    "93",
    "Provence-Alpes-Côte d'Azur",
    "43.3086",
    "5.3656",
)
LYON_ADDRESS = FictionalAddress(
    "12",
    "RUE",
    "DES LILAS",
    "69001",
    "LYON",
    "69381",
    "Rhône",
    "84",
    "Auvergne-Rhône-Alpes",
    "45.7676",
    "4.8344",
)

ACME_PLOMBERIE = FictionalCompany(
    siren="111111111",
    name="ACME PLOMBERIE",
    establishments=(FictionalEstablishment("00015", SHARED_ADDRESS, "2022-11-10"),),
    directors=(
        FictionalNaturalPerson("DUPONT", "Jean Pierre", "1980-05", "Président"),
        FictionalLegalPerson("HOLDING DUPONT", "Directeur général", "333333333"),
        FictionalLegalPerson("DUPONT INVEST LTD", "Associé"),
        FictionalNaturalPerson("LEROUX", "Camille", "1988-03", "Associé", diffusible=False),
    ),
    creation_date="2022-11-10",
)
DUPONT_SERVICES = FictionalCompany(
    siren="222222222",
    name="DUPONT SERVICES",
    establishments=(
        FictionalEstablishment("00015", SHARED_ADDRESS, "2019-04-02", closing_date="2023-01-15"),
    ),
    directors=(FictionalNaturalPerson("Dupont", "Jean", "1980-05", "Président"),),
    creation_date="2019-04-02",
    closing_date="2023-01-15",
)
HOLDING_DUPONT = FictionalCompany(
    siren="333333333",
    name="HOLDING DUPONT",
    establishments=(
        FictionalEstablishment("00015", HOLDING_ADDRESS, "2018-09-03", activity="70.10Z"),
    ),
    directors=(FictionalNaturalPerson("DUPONT", "Jean", "1980-05", "Président"),),
    creation_date="2018-09-03",
    activity="70.10Z",
    activity_section="M",
)
AUTRE_SOCIETE = FictionalCompany(
    siren="444444444",
    name="AUTRE SOCIETE",
    establishments=(
        FictionalEstablishment("00015", HOLDING_ADDRESS, "2017-06-12", activity="47.11B"),
    ),
    directors=(FictionalNaturalPerson("DUPONT", "Marie", "1975-02", "Gérante"),),
    creation_date="2017-06-12",
    activity="47.11B",
    activity_section="G",
    legal_form="5499",
)
LILAS_BOULANGERIE = FictionalCompany(
    siren="555555555",
    name="LILAS BOULANGERIE",
    establishments=(
        FictionalEstablishment("00015", LYON_ADDRESS, "2025-04-14", activity="10.71C"),
    ),
    directors=(FictionalNaturalPerson("MARTIN", "Paul", "1990-01", "Gérant"),),
    creation_date="2025-04-14",
    activity="10.71C",
    activity_section="C",
    legal_form="5499",
)
DUPONT_RENOVATION = FictionalCompany(
    siren="666666666",
    name="DUPONT RENOVATION",
    establishments=(
        FictionalEstablishment("00015", HOLDING_ADDRESS, "2023-02-20", activity="43.39Z"),
    ),
    directors=(FictionalNaturalPerson("DUPONT", "Jean Marc", "1980-05", "Gérant"),),
    creation_date="2023-02-20",
    activity="43.39Z",
    legal_form="5499",
)
HIDDEN_PLUMBER = FictionalCompany(
    siren="999999999",
    name="BLANC Hugo",
    establishments=(FictionalEstablishment("00015", SHARED_ADDRESS, "2023-03-01"),),
    directors=(FictionalNaturalPerson("BLANC", "Hugo", "1992-07", "Entrepreneur"),),
    creation_date="2023-03-01",
    legal_form="1000",
    diffusible=False,
)

FAKE_PLUMBERS_NOTICES = (
    FictionalNotice(
        "B202500010001",
        ACME_PLOMBERIE,
        "modification",
        "Modifications diverses",
        "2025-02-03",
        TOULOUSE_COURT,
        {
            "modificationsgenerales": {
                "descriptif": (
                    "Modification survenue sur l'administration. "
                    "Directeur général : HOLDING DUPONT"
                )
            }
        },
    ),
    FictionalNotice(
        "C202400020002",
        ACME_PLOMBERIE,
        "dpc",
        "Dépôts des comptes",
        "2024-07-12",
        TOULOUSE_COURT,
        {"depot": {"typeDepot": "Comptes annuels et rapports", "dateCloture": "2023-12-31"}},
    ),
    FictionalNotice(
        "A202200010003",
        ACME_PLOMBERIE,
        "immatriculation",
        "Immatriculations",
        "2022-11-24",
        TOULOUSE_COURT,
        {"acte": {"descriptif": "Société par actions simplifiée. Plomberie, chauffage."}},
    ),
    FictionalNotice(
        "B202300030001",
        DUPONT_SERVICES,
        "radiation",
        "Radiations",
        "2023-01-20",
        TOULOUSE_COURT,
        {"radiationaurcs": {"radiationPM": "Radiation du registre du commerce et des sociétés"}},
    ),
    FictionalNotice(
        "A202200030002",
        DUPONT_SERVICES,
        "collective",
        "Procédures collectives",
        "2022-12-05",
        TOULOUSE_COURT,
        {
            "jugement": {
                "type": "initial",
                "famille": "Jugement de clôture",
                "nature": "Jugement de clôture pour insuffisance d'actif",
                "date": "2022-11-28",
                "complementJugement": "Jugement prononçant la clôture de la procédure.",
            }
        },
    ),
    FictionalNotice(
        "A202200030003",
        DUPONT_SERVICES,
        "collective",
        "Procédures collectives",
        "2022-06-14",
        TOULOUSE_COURT,
        {
            "jugement": {
                "type": "initial",
                "famille": "Jugement d'ouverture",
                "nature": "Jugement d'ouverture de liquidation judiciaire",
                "date": "2022-06-07",
            }
        },
    ),
    FictionalNotice(
        "B202500040001",
        HOLDING_DUPONT,
        "modification",
        "Modifications diverses",
        "2025-09-18",
        MARSEILLE_COURT,
        {"modificationsgenerales": {"descriptif": "Transfert du siège social."}},
    ),
)

FAKE_PLUMBERS_SCENARIO = FictionalScenario(
    companies=(
        ACME_PLOMBERIE,
        DUPONT_SERVICES,
        HOLDING_DUPONT,
        AUTRE_SOCIETE,
        LILAS_BOULANGERIE,
        DUPONT_RENOVATION,
        HIDDEN_PLUMBER,
    ),
    notices=FAKE_PLUMBERS_NOTICES,
)
