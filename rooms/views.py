from rest_framework import exceptions
from rest_framework.viewsets import ViewSet, GenericViewSet
from rest_framework.response import Response
from rest_framework.decorators import action

from commons.requests import Request

from users.models import User

from .services import RoomService


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
