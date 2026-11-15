from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore


class PersonGroups:
    def __init__(self) -> None:
        self.parents: dict[str, str] = {}

    def join_decisions(self, decision_store: HomonymDecisionStore) -> None:
        for recorded in decision_store.decisions():
            if recorded.decision is HomonymDecision.SAME_PERSON:
                self.join(recorded.first_person, recorded.second_person)

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

    def pair_of(self, first_person: str, second_person: str) -> tuple[str, str]:
        first, second = sorted(
            (self.representative(first_person), self.representative(second_person))
        )
        return first, second
