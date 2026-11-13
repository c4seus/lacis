import httpx

from lacis.collectors.endpoints import BODACC_RECORDS_URL
from lacis.collectors.environment import (
    REAL_COLLECTION_ENVIRONMENT,
    demo_collection_environment,
)


def test_the_real_environment_uses_the_network() -> None:
    assert REAL_COLLECTION_ENVIRONMENT.transport is None
    assert not REAL_COLLECTION_ENVIRONMENT.demo


def test_the_demo_environment_answers_from_the_fake_plumbers_scenario() -> None:
    environment = demo_collection_environment()
    assert environment.demo
    with httpx.Client(transport=environment.transport) as client:
        response = client.get(BODACC_RECORDS_URL, params={"where": 'registre="222222222"'})
    assert response.json()["total_count"] == 3


def test_each_demo_environment_has_its_own_fake_api() -> None:
    assert demo_collection_environment().transport is not demo_collection_environment().transport
