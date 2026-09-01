from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException, NotFound, ValidationError
from django.utils import timezone

def custom_api_exception_handler(exc, context):
    """
    Standardises all API errors into the canonical Nomad Analyst error structure:
    {
      "error": {
        "code": "ERROR_CODE",
        "message": "Human readable error summary",
        "details": {},
        "timestamp": "ISO-8601 UTC"
      }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        code = getattr(exc, 'default_code', 'API_ERROR').upper()
        if isinstance(exc, NotFound):
            code = 'RESOURCE_NOT_FOUND'
        elif isinstance(exc, ValidationError):
            code = 'VALIDATION_ERROR'

        message = str(exc)
        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, str):
                message = exc.detail
            elif isinstance(exc.detail, dict):
                message = "Validation failed for one or more fields."
            elif isinstance(exc.detail, list) and len(exc.detail) > 0:
                message = str(exc.detail[0])

        details = response.data if isinstance(response.data, dict) else {'raw': response.data}

        response.data = {
            'error': {
                'code': code,
                'message': message,
                'details': details,
                'timestamp': timezone.now().isoformat()
            }
        }

    return response
