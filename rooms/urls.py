from rest_framework.routers import DefaultRouter
from .views import RoomsViewSet

router = DefaultRouter()
router.register("rooms", RoomsViewSet, "rooms")
