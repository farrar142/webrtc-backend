from typing import Concatenate
from uuid import uuid4
from pydantic import BaseModel, computed_field

from django.core.cache import cache
from rest_framework import exceptions

from commons.lock import with_lock


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
