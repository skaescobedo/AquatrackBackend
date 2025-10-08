from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError

def _normalize_errors(errs):
    norm = []
    for e in errs:
        e = dict(e)
        val = e.get("input")
        if isinstance(val, (bytes, bytearray)):
            try:
                e["input"] = val.decode("utf-8", errors="ignore")
            except Exception:
                e["input"] = repr(val)
        norm.append(e)
    return norm

def install_error_handlers(app: FastAPI):
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": _normalize_errors(exc.errors())},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_handler(request: Request, exc: IntegrityError):
        return JSONResponse(status_code=409, content={"error": "conflict", "detail": str(exc.orig)})
