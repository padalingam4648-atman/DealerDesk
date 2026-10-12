from rest_framework import status
from rest_framework.exceptions import APIException, ParseError, NotFound, MethodNotAllowed, NotAuthenticated, PermissionDenied
from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404


class DealerDeskAPIException(APIException):
    """Base API exception for DealerDesk with structured error code and message."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "BAD_REQUEST"
    default_detail = "A bad request occurred."

    def __init__(self, message=None, code=None, details=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.default_code = code
        self.code = self.default_code
        self.message = message or self.default_detail
        self.details = details if details is not None else []
        super().__init__(self.message, code=self.code)


class ValidationError(DealerDeskAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "VALIDATION_ERROR"
    default_detail = "Validation error."


class DuplicateError(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "DUPLICATE"
    default_detail = "Resource already exists."


class InsufficientStockError(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "INSUFFICIENT_STOCK"
    default_detail = "Insufficient stock available."


class InvalidTransitionError(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "INVALID_TRANSITION"
    default_detail = "Invalid status transition."


class OrderLockedError(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "ORDER_LOCKED"
    default_detail = "Order cannot be edited in its current status."


class IdempotencyConflictError(DealerDeskAPIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "IDEMPOTENCY_CONFLICT"
    default_detail = "Conflicting request payload with existing idempotency key."


class NotFoundError(DealerDeskAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "NOT_FOUND"
    default_detail = "Resource not found."


class SupplierUnavailableError(DealerDeskAPIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_code = "SUPPLIER_UNAVAILABLE"
    default_detail = "Supplier feed unavailable."


def flatten_details(detail_data):
    """Flatten DRF/Django detail structures into a clean list of strings/objects."""
    details = []
    if isinstance(detail_data, dict):
        for key, val in detail_data.items():
            if isinstance(val, (list, tuple)):
                for item in val:
                    msg = str(item)
                    details.append(f"{key}: {msg}" if key != "non_field_errors" else msg)
            elif isinstance(val, dict):
                sub_details = flatten_details(val)
                for sub in sub_details:
                    details.append(f"{key}.{sub}")
            else:
                details.append(f"{key}: {val}")
    elif isinstance(detail_data, (list, tuple)):
        for item in detail_data:
            if isinstance(item, (dict, list, tuple)):
                details.extend(flatten_details(item))
            else:
                details.append(str(item))
    elif detail_data is not None:
        details.append(str(detail_data))
    return details


def custom_exception_handler(exc, context):
    """
    Standard DRF exception handler producing DealerDesk contract error envelope:
    {"error": {"code": "...", "message": "human readable", "details": []}}
    """
    # Normalize Django built-ins to DRF
    if isinstance(exc, Http404):
        exc = NotFound()
    elif isinstance(exc, DjangoValidationError):
        exc = ValidationError(message="Validation failed", details=flatten_details(exc.message_dict if hasattr(exc, "message_dict") else exc.messages))
    elif isinstance(exc, IntegrityError):
        exc = DuplicateError(message="A resource with this identifier already exists.", details=[str(exc)])

    # Handle custom DealerDeskAPIException
    if isinstance(exc, DealerDeskAPIException):
        response_data = {
            "error": {
                "code": exc.code,
                "message": str(exc.message),
                "details": list(exc.details) if isinstance(exc.details, (list, tuple)) else [str(exc.details)],
            }
        }
        return Response(response_data, status=exc.status_code)

    # Call DRF's default exception handler to get standard Response
    response = exception_handler(exc, context)

    if response is not None:
        status_code = response.status_code
        code = "ERROR"
        message = "An error occurred."
        details = []

        if status_code == status.HTTP_400_BAD_REQUEST:
            # Check if any error is a uniqueness error
            is_unique = False
            if isinstance(response.data, dict):
                for k, v in response.data.items():
                    if isinstance(v, list):
                        for err in v:
                            if getattr(err, "code", None) == "unique" or "already exists" in str(err).lower():
                                is_unique = True
                                break
            if is_unique:
                status_code = status.HTTP_409_CONFLICT
                response.status_code = status.HTTP_409_CONFLICT
                code = "DUPLICATE"
                message = "Resource with this identifier already exists."
                details = flatten_details(response.data)
            else:
                code = "VALIDATION_ERROR"
                message = "Validation error."
                details = flatten_details(response.data)
                if details and len(details) == 1 and not details[0].startswith("non_field_errors"):
                    message = details[0]
                elif details and any("JSON parse error" in d for d in details):
                    message = "Malformed JSON input."
        elif status_code == status.HTTP_404_NOT_FOUND:
            code = "NOT_FOUND"
            message = "Not found."
            if isinstance(response.data, dict) and "detail" in response.data:
                message = str(response.data["detail"])
        elif status_code == status.HTTP_409_CONFLICT:
            code = "DUPLICATE"
            message = "Conflict."
            if isinstance(response.data, dict) and "detail" in response.data:
                message = str(response.data["detail"])
        elif status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            code = "METHOD_NOT_ALLOWED"
            message = "Method not allowed."
            if isinstance(response.data, dict) and "detail" in response.data:
                message = str(response.data["detail"])
        elif status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
            code = "FORBIDDEN"
            message = "Access denied."
            if isinstance(response.data, dict) and "detail" in response.data:
                message = str(response.data["detail"])
        elif status_code == status.HTTP_502_BAD_GATEWAY:
            code = "SUPPLIER_UNAVAILABLE"
            message = "Bad gateway."
        else:
            code = "SERVER_ERROR"
            message = "Server error."
            details = flatten_details(response.data)

        response.data = {
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        }
        return response

    return None
