from calendar import timegm

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from utils.email import send_recovery_email
from .utils import jwt_encode, jwt_decode, jwt_payload, generate_hash

jwt_settings = settings.JWT_SETTINGS
User = get_user_model()


class RefreshTokenQuerySet(models.QuerySet):

    def revoke_all_for_user(self, user):
        self.get_active_tokens_for_sub(user.id).update(revoked_at=timezone.now())

    def get_active_tokens_for_sub(self, sub, **kwargs):
        return self.filter_active_tokens(user__id=sub, **kwargs)

    def filter_active_tokens(self, **kwargs):
        created_at = timezone.now() - jwt_settings.get('REFRESH_TOKEN_EXPIRATION_DELTA')
        return self.filter(created_at__gt=created_at, revoked_at__isnull=True, **kwargs)

    def access_token_is_active(self, jti, **kwargs):
        return self.filter_active_tokens(jti=jti, **kwargs).exists()


class RefreshToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refresh_tokens')
    jti = models.CharField(max_length=255, editable=False)
    token = models.CharField(max_length=255, editable=False)
    created_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = RefreshTokenQuerySet.as_manager()

    class Meta:
        unique_together = ('token', 'created_at', 'jti')

    def __str__(self):
        return self.token

    @property
    def expires_at(self):
        return self.created_at + jwt_settings.get('REFRESH_TOKEN_EXPIRATION_DELTA')

    @property
    def is_expired(self):
        return self.expires_at > timezone.now()

    @property
    def is_revoked(self):
        return self.revoked_at is not None

    @property
    def is_active(self):
        return not (self.is_revoked or self.is_expired)

    def get_payload_by_token(self):
        return jwt_decode(self.token)

    @staticmethod
    def generate_jti(user, created_at):
        key = f'{user.id}-{timegm(created_at.utctimetuple())}'
        return generate_hash(key)

    def revoke(self):
        self.revoked_at = timezone.now()
        self.save()

    def save(self, *args, **kwargs):
        self.created_at = timezone.now()

        if not self.jti:
            self.jti = self.generate_jti(self.user, self.created_at)

        if not self.token:
            payload = jwt_payload(self.user, self.expires_at, self.jti, 'refresh')
            self.token = jwt_encode(payload)

        return super().save(*args, **kwargs)


class ResetToken(models.Model):
    token = models.CharField(max_length=255, editable=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reset_tokens')

    @property
    def is_expired(self):
        return timezone.now() < (self.created_at + settings.PASS_RESET_TOKEN_EXPIRATION_DELTA)

    @property
    def is_active(self):
        return self.is_expired and not self.is_used

    def set_password(self, password):
        self.is_used = True
        self.user.set_password(password)

    @staticmethod
    def generate_token(user, created_at):
        from users.jwt_auth.utils import generate_hash
        hash_key = f'{user.id} - {created_at.timestamp()}'
        return generate_hash(hash_key)

    def send_recovery_mail(self):
        send_recovery_email(
            self.user.first_name,
            self.user.last_name,
            self.token,
            self.user.email
        )

    def save(self, *args, **kwargs):

        if not self.created_at:
            self.created_at = timezone.now()

        if not self.token:
            self.token = self.generate_token(self.user, self.created_at)

        return super().save(*args, **kwargs)