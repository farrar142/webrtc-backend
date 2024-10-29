import json
from typing import Any, Literal, TypedDict
from asgiref.sync import async_to_sync, sync_to_async


from channels.layers import InMemoryChannelLayer
from channels.layers import get_channel_layer
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .services import RoomService


class Authentication(TypedDict):
    type: Literal["authentication"]
    password: str
    user_id: str
    username: str


class NotifyParticipant(TypedDict):
    type: Literal["notifyparticipant"]
    user_id: str
    username: str


class SendSDP(TypedDict):
    type: Literal["sendsdp"] | Literal["answersdp"]
    sender: str
    receiver: str
    sdp: str


class SendCandidate(TypedDict):
    type: Literal["sendcandidate"]
    sender: str
    receiver: str
    candidate: dict


class StreamStatus(TypedDict):
    type: Literal["streamstatus"]
    sender: str
    media: Literal["video"] | Literal["audio"]
    status: bool


class RoomConsumer(AsyncJsonWebsocketConsumer):
    channel_layer: InMemoryChannelLayer
    signed = False
    user_id: None | str

    def __init__(self, *args, **kwargs):
        self.user_id = None
        super().__init__(*args, **kwargs)

    @staticmethod
    def get_group_name(user_id: int | str):
        return f"message_user-{user_id}"

    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_id"]
        self.service = RoomService(self.room_name)
        self.group_name = self.get_group_name(self.room_name)
        if self.channel_layer:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if self.channel_layer:
            if self.user_id:
                await sync_to_async(self.service.remove_participant)(self.user_id)
                await self.channel_layer.group_send(
                    self.group_name,
                    dict(
                        type="emit",
                        data=dict(type="userdisconnected", user_id=self.user_id),
                    ),
                )
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def handle_authentication(self, content: Authentication):
        room = await sync_to_async(self.service.authenticate)(content["password"])
        if room == False:
            return await self.send_authentication_success(False, dict())
        elif room == "empty":
            room = await sync_to_async(self.service.create_room)(
                content["user_id"], content["password"]
            )
        participant = self.service.Participant(
            user_id=content["user_id"],
            username=content["username"],
            audio_on=False,
            video_on=False,
        )
        self.user_id = content["user_id"]
        room = await sync_to_async(self.service.add_participant)(participant)
        return await self.send_authentication_success(
            True, room.model_dump()["participants"]
        )

    async def send_authentication_success(self, result: bool, data: dict):
        await self.send_json(dict(type="authentication", result=result, data=data))

    async def handle_notify_participant(self, content: NotifyParticipant):
        if not self.user_id:
            return
        await self.channel_layer.group_send(
            self.group_name, dict(type="emit", data=content)
        )

    async def handle_send_sdp(self, content: SendSDP):
        if not self.user_id:
            return
        await self.channel_layer.group_send(
            self.group_name, dict(type="send_sdp", data=content)
        )

    async def handle_send_candidate(self, content: SendCandidate):
        if not self.user_id:
            return
        await self.channel_layer.group_send(
            self.group_name, dict(type="send_sdp", data=content)
        )

    async def handle_stream_status(self, content: StreamStatus):
        if not self.user_id:
            return
        await self.channel_layer.group_send(
            self.group_name, dict(type="send_to_others", data=content)
        )

    async def receive_json(
        self,
        content: Authentication | NotifyParticipant | SendSDP | SendCandidate,
        **kwargs,
    ):
        print(content["type"])
        if content["type"] == "authentication":
            await self.handle_authentication(content)
        elif content["type"] == "notifyparticipant":
            await self.handle_notify_participant(content)
        elif content["type"] == "sendsdp" or content["type"] == "answersdp":
            await self.handle_send_sdp(content)
        elif content["type"] == "sendcandidate":
            await self.handle_send_candidate(content)

    async def emit(self, data):
        await self.send_json(data["data"])

    async def send_sdp(self, data: dict):
        if not self.user_id:
            return
        d = data["data"]
        receiver_id = d["receiver"]
        if self.user_id != receiver_id:
            return
        await self.send_json(d)

    async def send_to_others(self, data: dict):
        if not self.user_id:
            return
        d = data["data"]
        sender_id = d["sender"]
        if self.user_id == sender_id:
            return
        await self.send_json(d)
