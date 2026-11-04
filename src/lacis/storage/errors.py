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


class NewerInvestigationError(InvestigationError):
    def __init__(self, name: str, version: int, supported_version: int) -> None:
        super().__init__(
            f"L'enquête « {name} » a été enregistrée par une version plus récente de Lacis "
            f"(format {version}, alors que cette version lit jusqu'au format "
            f"{supported_version}). Mettez Lacis à jour pour l'ouvrir."
        )
        self.name = name
        self.version = version
        self.supported_version = supported_version
