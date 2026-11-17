from lacis.identity.groups import PersonGroups
from lacis.identity.homonyms import Confidence, homonym_proposals
from lacis.storage.entities import LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecisionStore

PROPOSALS_TAKEN_AS_SAME = frozenset({Confidence.CERTAIN, Confidence.PROBABLE})


class PersonIdentities(PersonGroups):
    def __init__(
        self,
        graph_store: GraphStore,
        decision_store: HomonymDecisionStore,
        *,
        include_probable: bool = False,
    ) -> None:
        super().__init__()
        self.graph_store = graph_store
        self.join_decisions(decision_store)
        if include_probable:
            for proposal in homonym_proposals(graph_store, decision_store):
                if proposal.confidence in PROPOSALS_TAKEN_AS_SAME:
                    self.join(*proposal.pair.people)

    def directed_companies(self, director: str) -> set[str]:
        return {
            link.target
            for member in self.group_of(director)
            for link in self.graph_store.links_of(member)
            if link.kind is LinkKind.MANDATE and link.source == member
        }

    def directors_of(self, company: str) -> set[str]:
        return {
            self.representative(link.source)
            for link in self.graph_store.links_of(company)
            if link.kind is LinkKind.MANDATE and link.target == company
        }

    def common_directors(self, first_company: str, second_company: str) -> set[str]:
        return self.directors_of(first_company) & self.directors_of(second_company)
