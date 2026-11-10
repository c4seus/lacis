from dataclasses import dataclass

import httpx

from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import DEFAULT_TIMING, CollectorTiming


@dataclass(frozen=True)
class CollectionEnvironment:
    transport: httpx.BaseTransport | None = None
    demo: bool = False
    timing: CollectorTiming = DEFAULT_TIMING


REAL_COLLECTION_ENVIRONMENT = CollectionEnvironment()


def demo_collection_environment() -> CollectionEnvironment:
    return CollectionEnvironment(httpx.MockTransport(FakeApi(FAKE_PLUMBERS_SCENARIO)), demo=True)
