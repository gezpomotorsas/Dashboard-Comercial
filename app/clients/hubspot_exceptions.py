"""Excepciones del cliente HubSpot."""


class HubSpotClientError(Exception):
    """Error base del cliente HubSpot."""


class HubSpotAuthenticationError(HubSpotClientError):
    """Error 401 - credenciales inválidas."""


class HubSpotPermissionError(HubSpotClientError):
    """Error 403 - permisos insuficientes."""


class HubSpotNotFoundError(HubSpotClientError):
    """Error 404 - recurso no encontrado."""


class HubSpotRateLimitError(HubSpotClientError):
    """Error 429 - límite de tasa excedido."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class HubSpotRequestError(HubSpotClientError):
    """Error genérico de solicitud."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
