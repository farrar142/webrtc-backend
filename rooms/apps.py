from django.apps import AppConfig
from django.core.cache import cache


class RoomsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rooms"

    def ready(self) -> None:
        keys: list[str] = cache.keys("*")
        target = list(filter(lambda x: x.startswith("v3"), keys))
        cache.delete_many(target)
        return super().ready()
