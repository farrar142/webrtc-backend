from functools import partial, wraps
from typing import Iterable, Self, TYPE_CHECKING
from django.contrib.auth.models import AbstractBaseUser, UserManager, PermissionsMixin
from django.db import models

from commons.model_utils import make_property_field
from images.models import Image


class UserAbstract(AbstractBaseUser, PermissionsMixin):
    class Meta:
        abstract = True

    default_manager = UserManager[Self]()
    username = models.CharField(max_length=30, unique=True)
    nickname = models.CharField(max_length=255, default="")
    email = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    USERNAME_FIELD = "email"

    @classmethod
    @property
    def objects(cls):
        return cls.default_manager

    def __str__(self):
        return self.username

    @classmethod
    def concrete_queryset(
        cls, *args, replace: models.QuerySet[Self] | None = None, **kwargs
    ):

        qs = cls.objects
        if replace:
            qs = replace
        return qs.all()


class User(UserAbstract):
    is_protected = models.BooleanField(default=False)
    is_registered = models.BooleanField(default=False)
    registered_at = models.DateTimeField(null=True)
    bio = models.CharField(max_length=511, default="")
    header_image = models.ForeignKey(
        Image, on_delete=models.SET_NULL, null=True, related_name="header_users"
    )
    profile_image = models.ForeignKey(
        Image, on_delete=models.SET_NULL, null=True, related_name="profile_users"
    )

    followings_count = make_property_field(False)
    followers_count = make_property_field(False)

    is_following_to = make_property_field(False)
    is_followed_by = make_property_field(False)
    is_mutual_follow = make_property_field(False)

    following_at = make_property_field(None)
    followed_by_at = make_property_field(None)

    is_chat_bot = make_property_field(False)

    @classmethod
    def concrete_queryset(cls, user: AbstractBaseUser | None = None, *args, **kwargs):
        if user and not user.is_authenticated:
            user = None

        return (
            super().concrete_queryset(*args, **kwargs).select_related("profile_image")
        )


class ThirdPartyProvider(models.TextChoices):
    KAKAO = "kakao"


class ThirdPartyIntegration(models.Model):
    created_at = models.DateTimeField(auto_now=True)
    provider = models.CharField(max_length=64, choices=ThirdPartyProvider.choices)
    provider_id = models.PositiveBigIntegerField()
    provider_email = models.EmailField()
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="third_party_integrations"
    )
