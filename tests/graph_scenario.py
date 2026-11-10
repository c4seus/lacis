from dataclasses import dataclass
from datetime import date

from investigation_builder import InvestigationBuilder


@dataclass(frozen=True)
class PlumbersScenario:
    acme: str
    dupont_services: str
    holding: str
    invest: str
    jean_pierre: str
    jean: str
    acme_office: str
    dupont_office: str
    address: str


def plumbers_scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    address = builder.address("12 RUE DES LILAS 31000 TOULOUSE", postcode="31000")
    acme = builder.company("ACME PLOMBERIE", date(2021, 3, 1))
    dupont_services = builder.company(
        "DUPONT SERVICES", date(2019, 6, 1), closing_date=date(2023, 1, 15)
    )
    holding = builder.company("HOLDING DUPONT")
    invest = builder.foreign_company("DUPONT INVEST LTD")
    jean_pierre = builder.person("Jean Pierre", "DUPONT")
    jean = builder.person("Jean", "DUPONT")
    builder.mandate(jean_pierre, acme, "Président")
    builder.mandate(jean, dupont_services, "Président")
    builder.mandate(holding, acme, "Directeur général")
    builder.mandate(invest, acme, "Associé")
    acme_office = builder.establishment(acme, address)
    dupont_office = builder.establishment(dupont_services, address, closing_date=date(2023, 1, 15))
    builder.registered_office(acme, address)
    builder.registered_office(dupont_services, address)
    builder.same_person(jean, jean_pierre)
    return PlumbersScenario(
        acme,
        dupont_services,
        holding,
        invest,
        jean_pierre,
        jean,
        acme_office,
        dupont_office,
        address,
    )
