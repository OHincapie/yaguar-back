from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NotFoundError(Exception):
    def __init__(self, resource: str, id: str | int):
        self.resource = resource
        self.id = id


class ConflictError(Exception):
    def __init__(self, message: str):
        self.message = message


class BusinessError(Exception):
    def __init__(self, message: str):
        self.message = message


class UnauthorizedError(Exception):
    def __init__(self, message: str = "Unauthorized"):
        self.message = message


class ForbiddenError(Exception):
    """Authenticated, but not allowed to do this — distinct from
    UnauthorizedError (401, not authenticated at all)."""

    def __init__(self, message: str = "Forbidden"):
        self.message = message


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": f"{exc.resource} '{exc.id}' not found"},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.message})

    @app.exception_handler(BusinessError)
    async def business_handler(request: Request, exc: BusinessError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.message})

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_handler(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": exc.message})

    @app.exception_handler(ForbiddenError)
    async def forbidden_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": exc.message})
