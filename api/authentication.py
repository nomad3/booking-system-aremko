"""
API Key Authentication for Luna AI Assistant
"""

from rest_framework import authentication
from rest_framework import exceptions
from django.conf import settings


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Simple API Key authentication for external services like Luna AI.
    Expects header: X-API-Key: <key>
    """

    def authenticate(self, request):
        api_key = request.META.get('HTTP_X_API_KEY')

        if not api_key:
            return None

        # Get the expected API key from settings
        expected_key = getattr(settings, 'LUNA_API_KEY', None)

        if not expected_key:
            raise exceptions.AuthenticationFailed('API Key not configured')

        if api_key != expected_key:
            raise exceptions.AuthenticationFailed('Invalid API Key')

        # Return a tuple of (user, auth) - we'll use None for user
        # since this is service-to-service authentication
        return (None, api_key)

    def authenticate_header(self, request):
        return 'X-API-Key'