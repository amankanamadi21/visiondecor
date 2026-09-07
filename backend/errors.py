"""
Structured error taxonomy (brief PART 15: the system must never silently
produce misleading results, and every failure needs a meaningful, user-safe
message — never a raw stack trace or an unexplained 500).

Every raised ApiError becomes:
    { "error": { "code": "...", "message": "...", "details": {...}? } }
with an appropriate HTTP status. Unhandled exceptions are caught by the
generic handler and converted to error_code="internal_error" with a generic
message — the real exception is logged server-side, never leaked to the
client.
"""
from __future__ import annotations

import logging
import traceback

from flask import Flask, jsonify

logger = logging.getLogger("visiondecor")


class ApiError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str, status_code: int | None = None, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self) -> dict:
        payload = {"error": {"code": self.code, "message": self.message}}
        if self.details:
            payload["error"]["details"] = self.details
        return payload


# --- Common, named error constructors -------------------------------------
# Using named constructors (rather than scattering raw ApiError(...) calls)
# keeps error codes consistent across the codebase and gives the frontend a
# stable contract to switch on.

def validation_error(message: str, details: dict | None = None) -> ApiError:
    return ApiError("validation_error", message, status_code=400, details=details)


def unauthorized(message: str = "Authentication required") -> ApiError:
    return ApiError("unauthorized", message, status_code=401)


def forbidden(message: str = "You do not have access to this resource") -> ApiError:
    return ApiError("forbidden", message, status_code=403)


def not_found(message: str = "Resource not found") -> ApiError:
    return ApiError("not_found", message, status_code=404)


def conflict(message: str, details: dict | None = None) -> ApiError:
    return ApiError("conflict", message, status_code=409, details=details)


def unsupported_media(message: str = "Unsupported file type") -> ApiError:
    return ApiError("unsupported_media", message, status_code=415)


def payload_too_large(message: str = "File exceeds the maximum allowed size") -> ApiError:
    return ApiError("payload_too_large", message, status_code=413)


def service_unavailable(message: str, details: dict | None = None) -> ApiError:
    return ApiError("service_unavailable", message, status_code=503, details=details)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(err: ApiError):
        response = jsonify(err.to_dict())
        response.status_code = err.status_code
        return response

    @app.errorhandler(404)
    def _handle_404(err):  # noqa: ANN001
        return jsonify(not_found().to_dict()), 404

    @app.errorhandler(Exception)
    def _handle_unexpected(err: Exception):
        # Log the full traceback server-side; never expose it to the client.
        logger.error("Unhandled exception: %s\n%s", err, traceback.format_exc())
        generic = ApiError("internal_error", "Something went wrong. Please try again.", status_code=500)
        return jsonify(generic.to_dict()), 500
