import json
import unicodedata
from dataclasses import dataclass, field
from typing import Any

JsonObject = dict[str, Any]

NON_DIFFUSIBLE = "[NON-DIFFUSIBLE]"
ACTIVE_STATE = "A"
CLOSED_COMPANY_STATE = "C"
CLOSED_ESTABLISHMENT_STATE = "F"
DIFFUSIBLE_STATUS = "O"
PARTIALLY_DIFFUSIBLE_STATUS = "P"
NATURAL_PERSON_TYPE = "personne physique"
LEGAL_PERSON_TYPE = "personne morale"
FICTIONAL_EPCI = "200000000"
HEAD_OFFICE_FIELDS = (
    "a_opco",
    "activite_principale",
    "activite_principale_naf25",
    "activite_principale_registre_metier",
    "annee_tranche_effectif_salarie",
    "adresse",
    "caractere_employeur",
    "cedex",
    "code_pays_etranger",
    "code_postal",
    "commune",
    "complement_adresse",
    "coordonnees",
    "date_creation",
    "date_debut_activite",
    "date_fermeture",
    "date_mise_a_jour",
    "date_mise_a_jour_insee",
    "departement",
    "distribution_speciale",
    "epci",
    "est_siege",
    "etat_administratif",
    "geo_adresse",
    "geo_id",
    "indice_repetition",
    "latitude",
    "libelle_cedex",
    "libelle_commune",
    "libelle_commune_etranger",
    "libelle_pays_etranger",
    "libelle_voie",
    "liste_enseignes",
    "liste_finess",
    "liste_id_bio",
    "liste_idcc",
    "liste_id_organisme_formation",
    "liste_rge",
    "liste_uai",
    "longitude",
    "nom_commercial",
    "numero_voie",
    "dernier_numero_voie",
    "region",
    "siret",
    "statut_diffusion_etablissement",
    "tranche_effectif_salarie",
    "type_voie",
)
MATCHING_ESTABLISHMENT_FIELDS = (
    "a_opco",
    "activite_principale",
    "activite_principale_naf25",
    "ancien_siege",
    "annee_tranche_effectif_salarie",
    "adresse",
    "caractere_employeur",
    "code_postal",
    "commune",
    "date_creation",
    "date_debut_activite",
    "date_fermeture",
    "epci",
    "est_siege",
    "etat_administratif",
    "geo_id",
    "latitude",
    "libelle_commune",
    "liste_enseignes",
    "liste_finess",
    "liste_id_bio",
    "liste_idcc",
    "liste_id_organisme_formation",
    "liste_rge",
    "liste_uai",
    "longitude",
    "nom_commercial",
    "region",
    "siret",
    "statut_diffusion_etablissement",
    "tranche_effectif_salarie",
)
FALSE_COMPLEMENTS = (
    "convention_collective_renseignee",
    "egapro_renseignee",
    "est_achats_responsables",
    "est_alim_confiance",
    "est_association",
    "est_avocat",
    "est_bio",
    "est_entrepreneur_spectacle",
    "est_ess",
    "est_finess",
    "est_organisme_formation",
    "est_qualiopi",
    "est_rge",
    "est_siae",
    "est_societe_mission",
    "est_uai",
    "est_patrimoine_vivant",
    "bilan_ges_renseigne",
    "a_aide_minimis",
    "a_aide_ademe",
    "est_administration",
)
EMPTY_COMPLEMENTS = (
    "collectivite_territoriale",
    "liste_idcc",
    "liste_finess_juridique",
    "numero_rnf",
    "liste_id_organisme_formation",
    "identifiant_association",
    "statut_entrepreneur_spectacle",
    "type_siae",
    "est_service_public",
    "est_l100_3",
)
BODACC_NOTICE_URL = (
    "https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:{identifier}"
)
PUBLICATION_OF_FAMILY = {
    "creation": "A",
    "immatriculation": "A",
    "collective": "A",
    "vente": "A",
    "modification": "B",
    "radiation": "B",
    "dpc": "C",
    "conciliation": "A",
    "retablissement_professionnel": "A",
    "divers": "A",
}


def without_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def searchable(text: str) -> str:
    return without_accents(text).upper()


def spaced_siren(siren: str) -> str:
    return f"{siren[:3]} {siren[3:6]} {siren[6:]}"


@dataclass(frozen=True)
class FictionalAddress:
    number: str
    street_type: str
    street_name: str
    postcode: str
    city: str
    city_code: str
    department_name: str
    region_code: str
    region_name: str
    latitude: str
    longitude: str

    @property
    def department(self) -> str:
        return self.postcode[:2]

    @property
    def full_text(self) -> str:
        return f"{self.number} {self.street_type} {self.street_name} {self.postcode} {self.city}"


@dataclass(frozen=True)
class FictionalEstablishment:
    nic: str
    address: FictionalAddress
    creation_date: str
    closing_date: str | None = None
    activity: str = "43.22A"
    trade_name: str | None = None

    def siret(self, siren: str) -> str:
        return f"{siren}{self.nic}"

    def record(self, siren: str, is_head_office: bool, diffusible: bool) -> JsonObject:
        address = self.address
        street_details = {
            "numero_voie": address.number,
            "type_voie": address.street_type,
            "libelle_voie": address.street_name,
            "adresse": address.full_text,
            "latitude": address.latitude,
            "longitude": address.longitude,
            "coordonnees": f"{address.latitude},{address.longitude}",
        }
        if not diffusible:
            street_details = {
                "numero_voie": NON_DIFFUSIBLE,
                "type_voie": NON_DIFFUSIBLE,
                "libelle_voie": NON_DIFFUSIBLE,
                "adresse": f"{address.postcode} {address.city}",
                "latitude": NON_DIFFUSIBLE,
                "longitude": NON_DIFFUSIBLE,
                "coordonnees": NON_DIFFUSIBLE,
            }
        return {
            "a_opco": False,
            "activite_principale": self.activity,
            "activite_principale_naf25": self.activity,
            "activite_principale_registre_metier": None,
            "ancien_siege": False,
            "annee_tranche_effectif_salarie": "2023",
            "caractere_employeur": "O",
            "cedex": None,
            "code_pays_etranger": None,
            "code_postal": address.postcode,
            "commune": address.city_code,
            "complement_adresse": None,
            "date_creation": self.creation_date,
            "date_debut_activite": self.creation_date,
            "date_fermeture": self.closing_date,
            "date_mise_a_jour": None,
            "date_mise_a_jour_insee": "2025-10-01T08:00:00",
            "departement": address.department,
            "dernier_numero_voie": None,
            "distribution_speciale": None,
            "epci": FICTIONAL_EPCI,
            "est_siege": is_head_office,
            "etat_administratif": (
                ACTIVE_STATE if self.closing_date is None else CLOSED_ESTABLISHMENT_STATE
            ),
            "geo_adresse": None,
            "geo_id": None,
            "indice_repetition": None,
            "libelle_cedex": None,
            "libelle_commune": address.city,
            "libelle_commune_etranger": None,
            "libelle_pays_etranger": None,
            "liste_enseignes": None,
            "liste_finess": None,
            "liste_id_bio": None,
            "liste_idcc": None,
            "liste_id_organisme_formation": None,
            "liste_rge": None,
            "liste_uai": None,
            "nom_commercial": self.trade_name if diffusible else None,
            "region": address.region_code,
            "siret": self.siret(siren),
            "statut_diffusion_etablissement": (
                DIFFUSIBLE_STATUS if diffusible else PARTIALLY_DIFFUSIBLE_STATUS
            ),
            "tranche_effectif_salarie": "01",
            **street_details,
        }

    def head_office_record(self, siren: str, diffusible: bool) -> JsonObject:
        record = self.record(siren, True, diffusible)
        return {key: record[key] for key in HEAD_OFFICE_FIELDS}

    def matching_record(self, siren: str, is_head_office: bool, diffusible: bool) -> JsonObject:
        record = self.record(siren, is_head_office, diffusible)
        return {key: record[key] for key in MATCHING_ESTABLISHMENT_FIELDS}


@dataclass(frozen=True)
class FictionalNaturalPerson:
    last_name: str
    first_names: str
    birth_month: str
    role: str
    nationality: str = "Française"
    diffusible: bool = True

    def record(self, diffusible: bool) -> JsonObject:
        if not (diffusible and self.diffusible):
            return {
                "nom": NON_DIFFUSIBLE,
                "prenoms": NON_DIFFUSIBLE,
                "annee_de_naissance": None,
                "date_de_naissance": None,
                "qualite": self.role,
                "nationalite": None,
                "type_dirigeant": NATURAL_PERSON_TYPE,
            }
        return {
            "nom": self.last_name,
            "prenoms": self.first_names,
            "annee_de_naissance": self.birth_month[:4],
            "date_de_naissance": self.birth_month,
            "qualite": self.role,
            "nationalite": self.nationality,
            "type_dirigeant": NATURAL_PERSON_TYPE,
        }


@dataclass(frozen=True)
class FictionalLegalPerson:
    name: str
    role: str
    siren: str | None = None

    def record(self, diffusible: bool) -> JsonObject:
        return {
            "siren": self.siren,
            "denomination": self.name,
            "qualite": self.role,
            "type_dirigeant": LEGAL_PERSON_TYPE,
        }


FictionalDirector = FictionalNaturalPerson | FictionalLegalPerson


@dataclass(frozen=True)
class FictionalCompany:
    siren: str
    name: str
    establishments: tuple[FictionalEstablishment, ...]
    directors: tuple[FictionalDirector, ...]
    creation_date: str
    closing_date: str | None = None
    activity: str = "43.22A"
    activity_section: str = "F"
    legal_form: str = "5710"
    acronym: str | None = None
    diffusible: bool = True

    @property
    def head_office(self) -> FictionalEstablishment:
        return self.establishments[0]

    def establishment_record(self, establishment: FictionalEstablishment) -> JsonObject:
        is_head_office = establishment is self.head_office
        return establishment.matching_record(self.siren, is_head_office, self.diffusible)

    @property
    def vat_number(self) -> str:
        vat_key = (12 + 3 * (int(self.siren) % 97)) % 97
        return f"FR{vat_key:02d}{self.siren}"

    def record(self, matching_establishments: list[FictionalEstablishment]) -> JsonObject:
        shown_name = self.name if self.diffusible else NON_DIFFUSIBLE
        return {
            "siren": self.siren,
            "siren_conserve": None,
            "nom_complet": shown_name,
            "nom_raison_sociale": shown_name,
            "sigle": self.acronym if self.diffusible else None,
            "nombre_etablissements": len(self.establishments),
            "nombre_etablissements_ouverts": sum(
                establishment.closing_date is None for establishment in self.establishments
            ),
            "siege": self.head_office.head_office_record(self.siren, self.diffusible),
            "activite_principale": self.activity,
            "activite_principale_naf25": self.activity,
            "section_activite_principale": self.activity_section,
            "categorie_entreprise": "PME",
            "annee_categorie_entreprise": "2023",
            "caractere_employeur": "O",
            "tranche_effectif_salarie": "01",
            "annee_tranche_effectif_salarie": "2023",
            "date_creation": self.creation_date,
            "date_fermeture": self.closing_date,
            "date_mise_a_jour": "2025-10-01T08:00:00",
            "date_mise_a_jour_insee": "2025-10-01T08:00:00",
            "date_mise_a_jour_rne": "2025-09-30T12:00:00",
            "etat_administratif": (
                ACTIVE_STATE if self.closing_date is None else CLOSED_COMPANY_STATE
            ),
            "nature_juridique": self.legal_form,
            "statut_diffusion": (
                DIFFUSIBLE_STATUS if self.diffusible else PARTIALLY_DIFFUSIBLE_STATUS
            ),
            "opposition_diffusion_commerciale": False,
            "dirigeants": [director.record(self.diffusible) for director in self.directors],
            "matching_etablissements": [
                self.establishment_record(establishment)
                for establishment in matching_establishments
            ],
            "finances": None,
            "complements": {
                **dict.fromkeys(FALSE_COMPLEMENTS, False),
                **dict.fromkeys(EMPTY_COMPLEMENTS),
                "est_entrepreneur_individuel": self.legal_form == "1000",
            },
            "tva": [self.vat_number],
        }

    def searchable_text(self, establishment: FictionalEstablishment) -> str:
        record = self.record([])
        director_names = [
            str(director.get("nom") or director.get("denomination") or "")
            + " "
            + str(director.get("prenoms") or "")
            for director in record["dirigeants"]
        ]
        address = self.establishment_record(establishment)["adresse"]
        parts = [record["nom_complet"], record["sigle"] or "", *director_names, address]
        return searchable(" ".join(parts))


@dataclass(frozen=True)
class FictionalNotice:
    identifier: str
    company: FictionalCompany
    family: str
    family_label: str
    publication_date: str
    court: str
    details: dict[str, JsonObject] = field(default_factory=dict)

    def record(self) -> JsonObject:
        address = self.company.head_office.address
        publication = PUBLICATION_OF_FAMILY[self.family]
        detail_fields = (
            "listeetablissements",
            "jugement",
            "acte",
            "modificationsgenerales",
            "radiationaurcs",
            "depot",
            "listeprecedentexploitant",
            "listeprecedentproprietaire",
            "divers",
            "parutionavisprecedent",
        )
        return {
            "id": self.identifier,
            "publicationavis": publication,
            "parution": self.identifier[1:9],
            "dateparution": self.publication_date,
            "numeroannonce": int(self.identifier[-4:]),
            "typeavis": "annonce",
            "typeavis_lib": "Avis initial",
            "familleavis": self.family,
            "familleavis_lib": self.family_label,
            "numerodepartement": address.department,
            "departement_nom_officiel": address.department_name,
            "region_code": int(address.region_code),
            "region_nom_officiel": address.region_name,
            "tribunal": self.court,
            "commercant": self.company.name,
            "ville": address.city,
            "cp": address.postcode,
            "pdf_parution_subfolder": int(self.identifier[1:5]),
            "ispdf_unitaire": "false",
            "registre": [self.company.siren, spaced_siren(self.company.siren)],
            "listepersonnes": json.dumps(
                {
                    "personne": {
                        "typePersonne": "pm",
                        "denomination": self.company.name,
                        "numeroImmatriculation": {
                            "numeroIdentification": spaced_siren(self.company.siren),
                            "codeRCS": "RCS",
                            "nomGreffeImmat": address.city,
                        },
                    }
                },
                ensure_ascii=False,
            ),
            **{
                detail_field: (
                    json.dumps(self.details[detail_field], ensure_ascii=False)
                    if detail_field in self.details
                    else None
                )
                for detail_field in detail_fields
            },
            "url_complete": BODACC_NOTICE_URL.format(identifier=self.identifier),
        }


@dataclass(frozen=True)
class FictionalScenario:
    companies: tuple[FictionalCompany, ...]
    notices: tuple[FictionalNotice, ...]
