from typing import Concatenate
from uuid import uuid4
from django.core.cache import cache

from rest_framework import exceptions
from rest_framework.viewsets import ViewSet, GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action

from commons.lock import with_lock
from commons.requests import Request
from commons.permissions import AuthorizedOnly
from pydantic import BaseModel, computed_field

from users.models import User


class Participant(BaseModel):
    user_id: str
    username: str
    audio_on: bool
    video_on: bool


class Room(BaseModel):
    password: str | None
    room_id: str | None
    owner: str
    participants: list[Participant] = []

    @computed_field
    @property
    def has_password(self) -> bool:
        return bool(self.password)


class RoomService:
    Participant = Participant
    Room = Room

    def __init__(self, room_name: str):
        self.room_name = room_name
        self.room_key = f"v3:rooms:{self.room_name}"

    def authenticate(self, password: str):
        if room := self.get_room_info():
            if room.password and room.password != password:
                return False
            return room
        return "empty"

    @with_lock["Concatenate[RoomService,str,str,...]", Room](
        lambda self, user, password: self.room_key
    )
    def create_room(self, user_id: str, password: str):
        if not (authenticate := self.authenticate(password)):
            raise exceptions.ValidationError(
                dict(password=["패스워드가 일치하지 않습니다."])
            )
        if isinstance(authenticate, Room):
            return authenticate

        room = Room(password=password, owner=user_id, room_id=str(uuid4()))
        cache.set(self.room_key, room.model_dump(), timeout=None)
        return room

    def get_room_info(self):
        if room := cache.get(self.room_key, None):
            return Room(**room)
        return False

    def drop_room(self):
        return cache.delete(self.room_key)

    def add_participant(self, participant: Participant):
        if not (room := self.get_room_info()):
            raise
        if not next(
            filter(lambda x: x.user_id == participant.user_id, room.participants), None
        ):
            room.participants.append(participant)
            cache.set(self.room_key, room.model_dump(), timeout=None)
        return room

    def remove_participant(self, user_id: str):
        if not (room := self.get_room_info()):
            raise
        room.participants = list(
            filter(lambda x: x.user_id != user_id, room.participants)
        )
        cache.set(self.room_key, room.model_dump(), timeout=None)


class RoomsViewSet(ViewSet):
    request: Request[User]

    @property
    def room_name(self):
        if name := self.kwargs.get("room"):
            return name
        raise exceptions.NotFound

    @action(methods=["POST"], detail=False, url_path=r"(?P<room>[\w-]+)")
    def get_room(self, *args, **kwargs):
        password = self.request.data.get("password", "")
        if not (user_id := self.request.data.get("user_id")):
            raise exceptions.NotAuthenticated
        if room := RoomService(self.room_name).get_room_info():
            print(password, room.password)
            if room.password != password:
                raise exceptions.ValidationError(
                    dict(password=["패스워드가 일치하지 않습니다"])
                )
            return Response(room.model_dump(exclude={"password"}))
        return Response(status=404)
