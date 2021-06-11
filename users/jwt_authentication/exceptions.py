from django.utils.translation import gettext_lazy as _


class JSONWebTokenError(Exception):
    default_message = None

    def __init__(self, message=None):
        if message is None:
            message = self.default_message

        super().__init__(message)


class PermissionDenied(JSONWebTokenError):
    default_message = _('You do not have permission to perform this action')


class JSONWebTokenExpired(JSONWebTokenError):
    default_message = _('Signature has expired')


class InvalidCredentials(JSONWebTokenError):
    default_message =  _('Invalid credentials')
