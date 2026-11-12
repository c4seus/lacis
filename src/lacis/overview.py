import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field

from lacis.graph.drawing import GraphDrawing, graph_drawing
from lacis.graph.leads import Lead, unexpanded_leads
from lacis.identity.homonyms import HomonymProposal, homonym_proposals
from lacis.signals.configuration import SignalConfigurationError
from lacis.signals.engine import SignalEngine
from lacis.signals.recomputation import InvestigationSignals
from lacis.signals.store import SignalReport
from lacis.storage.entities import LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.investigations import InvestigationLibrary


@dataclass(frozen=True)
class InvestigationOverview:
    entities: int
    links: int
    confirmed_homonyms: int
    report: SignalReport | None
    signal_problem: str = ""
    drawing: GraphDrawing = field(default_factory=GraphDrawing)
    proposals: tuple[HomonymProposal, ...] = ()
    unexpanded: tuple[Lead, ...] = ()

    @property
    def pending_homonyms(self) -> int:
        return len(self.proposals)

    @property
    def leads(self) -> int:
        return len(self.unexpanded)

    @property
    def signals(self) -> int | None:
        return None if self.report is None else len(self.report.signals)


def overview_of(
    connection: sqlite3.Connection, engine: SignalEngine | None, signal_problem: str = ""
) -> InvestigationOverview:
    graph_store = GraphStore(connection)
    decision_store = HomonymDecisionStore(connection)
    links = [link for link in graph_store.links() if link.kind is not LinkKind.SAME_PERSON]
    report = InvestigationSignals(connection, engine).current() if engine else None
    confirmed = [
        recorded
        for recorded in decision_store.decisions()
        if recorded.decision is HomonymDecision.SAME_PERSON
    ]
    return InvestigationOverview(
        entities=len(graph_store.entities()),
        links=len(links),
        confirmed_homonyms=len(confirmed),
        report=report,
        signal_problem=signal_problem,
        drawing=graph_drawing(connection, report),
        proposals=tuple(homonym_proposals(graph_store, decision_store)),
        unexpanded=tuple(unexpanded_leads(graph_store)),
    )


def read_overview(
    library: InvestigationLibrary,
    name: str,
    engine_factory: Callable[[], SignalEngine] = SignalEngine.configured,
) -> InvestigationOverview:
    try:
        engine: SignalEngine | None = engine_factory()
        problem = ""
    except SignalConfigurationError as refused:
        engine = None
        problem = str(refused)
    with library.open(name) as opened:
        return overview_of(opened.connection, engine, problem)
