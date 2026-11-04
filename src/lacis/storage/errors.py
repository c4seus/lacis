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


class InvestigationNotFoundError(InvestigationError):
    def __init__(self, name: str) -> None:
        super().__init__(f"L'enquête « {name} » est introuvable.")
        self.name = name


class InvestigationNotTrashedError(InvestigationError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Impossible de placer l'enquête « {name} » dans la corbeille.")
        self.name = name
