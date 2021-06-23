from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import AnonymousUser

from .models import RefreshToken
from .utils import get_refresh_token_by_request
from .exceptions import InvalidCredentials

jwt_settings = settings.JWT_SETTINGS


class TokenAuthenticationMiddleware:

    @staticmethod
    def _authenticate(context, user, refresh_token):
        context.user = user
        context.refresh_token = refresh_token

    @staticmethod
    def get_refresh_token_instance(refresh_token):
        refresh_token_qs = RefreshToken.objects.filter(token=refresh_token)

        if refresh_token_qs.exists():
            return refresh_token_qs[0]

        return None

    def resolve(self, next, root, info, **kwargs):
        context = info.context
        refresh_token = get_refresh_token_by_request(context)
        refresh_token_instance = self.get_refresh_token_instance(refresh_token)
        user = authenticate(request=context)

        if user is not None and refresh_token_instance is not None:
            if refresh_token_instance.user != user:
                raise InvalidCredentials('Refresh token is not valid')

            context.user = user
            context.refresh_token = refresh_token_instance

        else:
            context.user = AnonymousUser()
            context.refresh_token = None

        return next(root, info, **kwargs)



