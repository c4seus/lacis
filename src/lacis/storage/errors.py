class InvestigationError(Exception):
    pass


class InvalidInvestigationNameError(InvestigationError):
    pass


class InvalidInvestigationQuestionError(InvestigationError):
    pass


class InvestigationAlreadyExistsError(InvestigationError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Une enquête nommée « {name} » existe déjà.")
        self.name = name
