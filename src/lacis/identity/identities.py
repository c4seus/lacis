from lacis.identity.homonyms import Confidence, homonym_proposals
from lacis.storage.entities import LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore

PROPOSALS_TAKEN_AS_SAME = frozenset({Confidence.CERTAIN, Confidence.PROBABLE})


class PersonIdentities:
    def __init__(
        self,
        graph_store: GraphStore,
        decision_store: HomonymDecisionStore,
        *,
        include_probable: bool = False,
    ) -> None:
        self.graph_store = graph_store
        self.parents: dict[str, str] = {}
        for recorded in decision_store.decisions():
            if recorded.decision is HomonymDecision.SAME_PERSON:
                self.join(recorded.first_person, recorded.second_person)
        if include_probable:
            for proposal in homonym_proposals(graph_store, decision_store):
                if proposal.confidence in PROPOSALS_TAKEN_AS_SAME:
                    self.join(*proposal.pair.people)

    def representative(self, person: str) -> str:
        parent = self.parents.get(person, person)
        if parent == person:
            return person
        root = self.representative(parent)
        self.parents[person] = root
        return root

    def join(self, first_person: str, second_person: str) -> None:
        first_root = self.representative(first_person)
        second_root = self.representative(second_person)
        if first_root != second_root:
            low, high = sorted((first_root, second_root))
            self.parents[high] = low

    def same_person(self, first_person: str, second_person: str) -> bool:
        return self.representative(first_person) == self.representative(second_person)

    def group_of(self, person: str) -> frozenset[str]:
        root = self.representative(person)
        members = {member for member in self.parents if self.representative(member) == root}
        return frozenset({person, root, *members})

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
