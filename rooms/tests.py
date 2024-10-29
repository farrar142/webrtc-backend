from django.core.cache import cache
from rest_framework import exceptions
from base.test import TestCase
from users.models import User
from .services import RoomService


# Create your tests here.
class TestRooms(TestCase):
    user: User
    user2: User

    def setUp(self):
        super().setUp()
        self.service = RoomService("test")

    def tearDown(self) -> None:
        self.service.drop_room()
        return super().tearDown()

    def test_rooms_not_exists(self):
        resp = self.client.post(f"/rooms/{self.service.room_name}/")
        self.assertEqual(resp.status_code, 401)

    def test_create_room(self):
        # create room은 websocket이 연결 된 이후에 생성되어야됨
        resp = self.client.post(
            f"/rooms/{self.service.room_name}/", dict(password="1234")
        )
        self.assertEqual(resp.status_code, 401)
        resp = self.client.post(
            f"/rooms/{self.service.room_name}/",
            dict(password="1234", user_id=str(self.user.pk)),
        )
        self.assertEqual(resp.status_code, 404)

    def test_normal_rooms_exists(self):
        r1 = self.service.create_room(str(self.user.pk), "")
        resp = self.client.post(
            f"/rooms/{self.service.room_name}/",
            dict(user_id=str(self.user.pk), password=""),
        )
        self.assertEqual(resp.status_code, 200)
        r2 = self.service.create_room(str(self.user2.pk), "")
        self.assertEqual(r1, r2)

    def test_password_rooms_exists(self):
        r1 = self.service.create_room(str(self.user.pk), "test1234")
        resp = self.client.post(
            f"/rooms/{self.service.room_name}/", dict(user_id=str(self.user.pk))
        )
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(
            f"/rooms/{self.service.room_name}/",
            dict(password="test1234", user_id=str(self.user.pk)),
        )
        self.assertEqual(resp.status_code, 200)
        r2 = self.service.create_room(str(self.user2.pk), "test1234")
        self.assertEqual(r1, r2)
        with self.assertRaises(exceptions.ValidationError):
            self.service.create_room(str(self.user2.pk), "test12345")
