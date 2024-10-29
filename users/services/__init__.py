from uuid import uuid4
from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import localtime
from django.db.transaction import atomic
import requests
from rest_framework import serializers, exceptions

from commons.requests import Request
from commons.authentication import (
    CustomTokenObtainPairSerializer as TokenS,
    RefreshToken,
)
from commons.lock import with_lock

from ..models import User, ThirdPartyIntegration, ThirdPartyProvider
from ..tasks import send_register_email


class KakaoAuthorizationSerializer(serializers.Serializer):
    code = serializers.CharField()
    redirect_uri = serializers.URLField()


class SigninSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8)


class SignupSerializer(SigninSerializer):
    nickname = serializers.CharField(min_length=2, max_length=64, required=False)
    username = serializers.CharField(min_length=2, max_length=64)
    password2 = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    access = serializers.CharField()


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class CodeKeySerializer(serializers.Serializer):
    code_key = serializers.CharField()


class AuthService:
    def __init__(self, user: User):
        self.user = user

    @classmethod
    def get_kakao_user(cls, code: str, redirect_uri: str):
        resp = requests.post(
            "https://kauth.kakao.com/oauth/token",
            dict(
                code=code,
                client_id=settings.KAKAO_CLIENT_KEY,
                client_secret=settings.KAKAO_SECRET_KEY,
                redirect_uri=redirect_uri,
                grant_type="authorization_code",
            ),
        )
        if resp.status_code != 200:
            raise exceptions.ValidationError(detail=resp.json())
        access_token = resp.json().get("access_token")
        resp = requests.get(
            "https://kapi.kakao.com/v2/user/me",
            headers=dict(Authorization=f"Bearer {access_token}"),
        )
        return resp.json()

    @classmethod
    @atomic()
    def signin_kakao(cls, code: str, redirect_uri: str):
        resp = cls.get_kakao_user(code, redirect_uri)
        kakao_id, nickname = resp["id"], resp["kakao_account"]["profile"]["nickname"]
        temp_email = str(kakao_id) + "@" + "kakao.com"
        if not (
            user := User.objects.filter(
                third_party_integrations__provider_email=temp_email
            ).first()
        ):
            user = User(
                email=temp_email, username=f"kakao_{kakao_id}", nickname=nickname
            )
            user.is_registered = True
            user.registered_at = localtime()
            user.set_password(None)
            user.save()
            integration = ThirdPartyIntegration(
                provider=ThirdPartyProvider.KAKAO,
                provider_id=kakao_id,
                provider_email=temp_email,
                user=user,
            )
            integration.save()
        refresh = TokenS.get_token(user)
        access = str(refresh.access_token)
        return dict(refresh=str(refresh), access=access)

    @classmethod
    def signin(cls, email: str, password: str):
        if not (user := User.objects.filter(email=email).first()):
            raise exceptions.NotFound(dict(email=["Email Not Found"]))
        if not user.check_password(password):
            raise exceptions.AuthenticationFailed(dict(password=["Wrong Password"]))
        refresh = TokenS.get_token(user)
        access = str(refresh.access_token)  # type:ignore
        return dict(refresh=str(refresh), access=access)

    @classmethod
    def refresh(cls, refresh: str):
        try:
            token: RefreshToken = TokenS.token_class(token=refresh)  # type:ignore
            return dict(access=str(token.access_token), refresh=str(token))
        except:
            exception = exceptions.APIException()
            exception.detail = dict(detail=["expired token"], code="invalid_token")
            exception.status_code = 400
            raise exception

    @classmethod
    def signup(
        cls,
        email: str,
        username: str,
        password: str,
        password2: str,
        nickname: str | None = None,
    ):

        with with_lock(f"signup:{email}"):
            if User.objects.filter(email=email).first():
                raise exceptions.ValidationError(dict(email=["Duplicated Email"]))
            if User.objects.filter(username=username).first():
                raise exceptions.ValidationError(dict(username=["Duplicated Username"]))
            if password != password2:
                raise exceptions.ValidationError(
                    dict(
                        password=["Password not matched"],
                        password2=["Password not matched"],
                    )
                )
            user = User().objects.create_user(
                username, email, password, nickname=nickname or username
            )
        refresh = TokenS.get_token(user)
        access = str(refresh.access_token)  # type:ignore
        return user, dict(refresh=str(refresh), access=access)

    def send_register_email(self):
        already_key = f"email_sent:{self.user.pk}"
        if cache.get(already_key, True, 3 * 60):
            raise exceptions.ValidationError(
                dict(email=["Try after three minutes later"])
            )
        cache.set(already_key, True)
        code_key = str(uuid4())
        cache_key = f"register:{code_key}"
        cache.set(cache_key, self.user.pk, 60 * 60)
        send_register_email.delay(user_id=self.user.pk, code_key=code_key)
        return code_key

    @classmethod
    def register_user(cls, code_key: str):
        cache_key = f"register:{code_key}"
        user_id = cache.get(cache_key, None)
        if not user_id:
            raise exceptions.ValidationError(dict(code_key=["Key not found"]))
        cache.delete(cache_key)
        user = User.objects.filter(pk=user_id).first()
        if not user:
            raise exceptions.ValidationError(dict(code_key=["User not found"]))
        user.is_registered = True
        user.registered_at = localtime()
        user.save()

        refresh = TokenS.get_token(user)
        access = str(refresh.access_token)  # type:ignore
        return dict(refresh=str(refresh), access=access)
