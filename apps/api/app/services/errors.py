class DomainError(Exception):
    """A rule of the product was violated. Message is shown to the user or the LLM."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


class NotFound(DomainError):
    def __init__(self, what: str = "Ressource"):
        super().__init__(f"{what} introuvable.", 404)
