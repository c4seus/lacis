import sqlite3
from datetime import date

import pytest

from investigation_builder import InvestigationBuilder
from lacis.graph.roles import DirectorRole
from lacis.signals.configuration import load_configuration
from lacis.signals.rule_settings import RuleSettings
from lacis.signals.rules import RULES
from lacis.signals.rules.directors import excluded_roles, mandates


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def settings() -> RuleSettings:
    return load_configuration(RULES)["short_lived_companies"]


def test_excluded_roles_are_read_as_director_roles(settings: RuleSettings) -> None:
    assert excluded_roles(settings) == {
        DirectorRole.STATUTORY_AUDITOR,
        DirectorRole.ALTERNATE_AUDITOR,
        DirectorRole.COURT_ADMINISTRATOR,
        DirectorRole.COURT_REPRESENTATIVE,
        DirectorRole.COURT_LIQUIDATOR,
    }


def test_mandates_give_each_director_of_a_company_with_its_identity(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    company = builder.company("SOCIETE A", date(2024, 1, 10))
    builder.mandate(director, company)
    auditor = builder.person("Claire", "AUDIT")
    builder.mandate(auditor, company, "Commissaire aux comptes titulaire")
    [mandate] = mandates(builder.context(), settings)
    assert (mandate.director.identifier, mandate.company.identifier, mandate.identity) == (
        director,
        company,
        director,
    )
