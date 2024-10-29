from contextlib import contextmanager
import functools
import time
from typing import (
    Any,
    Callable,
    Concatenate,
    Generic,
    Literal,
    Mapping,
    ParamSpec,
    Self,
    TypeVar,
)
from django.conf import settings
from django.http.response import HttpResponse
from django.test import TestCase as TC, Client as C
from django.contrib.auth import get_user_model

from commons.authentication import CustomTokenObtainPairSerializer

from pprint import pprint as pp

P = ParamSpec("P")
T = TypeVar("T")

User = get_user_model()


def header_override():
    def decorator(func: Callable[Concatenate["Client", P], T]):
        def wrapper(self, *args: P.args, **kwargs: P.kwargs) -> T:
            kwargs["headers"] = self._headers  # type:ignore
            result = func(self, *args, **kwargs)
            result.show = lambda: pp(result.json())  # type:ignore
            return result

        return wrapper

    return decorator


class Client(C):
    _headers = dict()

    def login(self, user: Any):
        refresh = CustomTokenObtainPairSerializer.get_token(user)
        access = str(refresh.access_token)  # type:ignore
        self._headers = dict(AUTHORIZATION=f"Bearer {access}")
        return access, str(refresh)

    @header_override()
    def get(self, *args, **kwargs):
        return super().get(*args, **kwargs)

    @header_override()
    def post(self, *args, **kwargs):
        return super().post(content_type="application/json", *args, **kwargs)

    @header_override()
    def patch(self, *args, **kwargs):
        return super().patch(content_type="application/json", *args, **kwargs)

    @header_override()
    def delete(self, *args, **kwargs):
        return super().delete(*args, **kwargs)


from django.conf import settings
from django.db import connection

P = ParamSpec("P")
T = TypeVar("T")


def record_query(func: Callable[P, T]):
    # default_setting = settings.DEBUG
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs):
        # connection.queries = []
        result = func(*args, **kwargs)
        after_queries = len(connection.queries)
        print(f"{func.__name__} execed in {after_queries} queries")
        pp(connection.queries)
        return result

    return wrapper


E = TypeVar("E")
B = TypeVar("B", bound=bool)
ErrorType = dict[str, Exception]


class ErrorContainer(Generic[E, B]):
    detail: E
    is_error: B

    def __init__(self, data, is_error: B):
        self.is_error = is_error
        if self.is_error:
            self.detail = data
        else:
            self.detail = data


class TestCase(TC):
    client_class = Client
    client: Client = Client()

    # @contextmanager
    # def exception_catcher(self, error: type[Exception]):
    #     try:
    #         yield True
    #     except error:
    #         return
    #     except:
    #         self.assertRaises
    #         self.assertEqual(True, False)
    #     self.assertEqual(True, False)

    @property
    def record_query(self):
        return record_query

    def __init__(self, methodName: str = "runTest") -> None:
        settings.DEBUG = True
        super().__init__(methodName)

    def setUp(self):
        settings.DEBUG = True
        User = get_user_model()
        user = User(username="test", email="test@gmail.com", nickname="test")
        user.set_password("1234567890")
        user2 = User(username="test2", email="test2@gmail.com", nickname="test2")
        user2.set_password("1234567890")
        user3 = User(username="test3", email="test3@gmail.com", nickname="test3")
        user3.set_password("1234567890")
        users = User.objects.bulk_create([user, user2, user3])
        self.user = users[0]
        self.user2 = users[1]
        self.user3 = users[2]

    def pprint(self, *args, **kwargs):
        pp(*args, **kwargs)

    def aware_error(
        self, func: Callable[P, T]
    ) -> Callable[
        P, ErrorContainer[T, Literal[False]] | ErrorContainer[ErrorType, Literal[True]]
    ]:
        @functools.wraps(func)
        def wrapper(
            *args: P.args, **kwargs: P.kwargs
        ) -> (
            ErrorContainer[T, Literal[False]] | ErrorContainer[ErrorType, Literal[True]]
        ):
            try:
                return ErrorContainer[T, Literal[False]](func(*args, **kwargs), False)
            except Exception as e:
                return ErrorContainer[ErrorType, Literal[True]](e, True)

        return wrapper
