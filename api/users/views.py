import os

import urllib

from datetime import timedelta, datetime

from tempfile import NamedTemporaryFile

import requests

import dotenv

from django.http import HttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.core.files import File
from django.contrib.auth import login
from django.utils.decorators import method_decorator

from rest_framework import exceptions, permissions, parsers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_json_api import views, serializers

from oauth2_provider.models import AccessToken, RefreshToken
from oauth2_provider.views import AuthorizationView

from oauthlib import common

from django_ratelimit.decorators import ratelimit

from PIL import Image

from utils import get_or_none
from utils.decorators import permission_classes

from applications.models import Application

from .models import User, DiscordUser, Domain
from .serializers import UserPublicSerializer, UserPrivateSerializer, DomainSerializer

dotenv.load_dotenv()

# Create your views here.


def get_client_ip(request) -> str:
    """
    Returns the original client IP.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def validate_recaptcha(request) -> bool:
    """
    Validates a reCAPTCHA challenge and returns wether it has been successful
    or not.
    """
    r = requests.post(
        "https://www.google.com/recaptcha/api/siteverify?"
        + urllib.parse.urlencode(
            {
                "response": request.POST.get("g-recaptcha-response"),
                "secret": os.getenv("RECAPTCHA_SECRET_KEY"),
                "remoteip": get_client_ip(request),
            }
        )
    )
    return r.json()["success"]


@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="list")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="retrieve")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="retrieve_related")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="update")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="follow")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="unfollow")
class UserView(views.ModelViewSet):
    queryset = User.objects.all()
    select_for_includes = {"discord": ["discord"]}
    prefetch_for_includes = {
        "liked_images": ["liked_images"],
        "saved_images": ["saved_images"],
        "following": ["following"],
        "followed": ["followed"],
        "followed_artists": ["followed_artists"],
        "followed_characters": ["followed_characters"],
        "followed_categories": ["followed_categories"],
        "followed_lists": ["followed_lists"],
    }
    filterset_fields = {
        "discord__id": [
            "exact"
        ]
    }

    def get_serializer_class(self):
        if (self.request.user.is_authenticated and self.kwargs.get("pk") == "@me") or (
            self.request.user.is_authenticated
            and str(self.kwargs.get("pk")) == str(self.request.user.id)
        ):
            return UserPrivateSerializer
        return UserPublicSerializer

    def get_object(self):
        if (self.request.user.is_authenticated and self.kwargs.get("pk") == "@me") or (
            self.request.user.is_authenticated
            and self.kwargs.get("pk") == str(self.request.user.id)
        ):
            return self.request.user
        elif not self.request.user.is_authenticated and self.kwargs.get("pk") == "@me":
            raise exceptions.NotAuthenticated()
        else:
            return User.objects.get(pk=self.kwargs.get("pk"))

    def signup(self, request):
        """
        Sign up a user.
        """

        if (
            request.headers.get("Authorization")
            != "Token " + settings.PROTECTED_API_TOKEN
        ):
            return HttpResponse(content="", status=401)

        user = User(
            username=request.POST.get("username"),
            email=request.POST.get("email"),
            first_name=request.POST.get("firstName"),
            last_name=request.POST.get("lastName"),
            is_active=False,
        )
        user.set_password(request.POST.get("password"))
        user.save()

        return Response(UserPrivateSerializer(data=user))

    @permission_classes([permissions.IsAuthenticated])
    def update(self, request, *args, **kwargs):
        """
        Edit a user.
        """

        user = self.get_object()

        if request.user != user:
            raise serializers.ValidationError(
                detail="You cannot update another user's data!",
                code="cannot_update_unauthenticated_user",
            )

        response = super().update(request, *args, **kwargs)

        response.headers[
            "X-Avatar-Upload-Location"
        ] = "https://api.nekosapi.com/v2/users/@me/avatar"

        return response

    def retrieve_related(self, request, pk, related_field, *args, **kwargs):
        """
        Verifies that the request is not trying to access private
        endpoints.
        """
        if related_field in ["saved-images", "discord"]:
            if not request.user.is_authenticated:
                raise exceptions.NotAuthenticated()
            elif str(request.user.pk) != str(pk):
                raise serializers.ValidationError(
                    detail="You cannot see this information.", code="forbidden"
                )

        return super().retrieve_related(
            request, pk=pk, related_field=related_field, *args, **kwargs
        )

    @permission_classes([permissions.IsAuthenticated])
    def follow(self, request, *args, **kwargs):
        """
        Follow a user.
        """

        user = self.get_object()

        if user == request.user:
            raise serializers.ValidationError(
                {
                    "id": "self_follow_forbidden",
                    "detail": "You followed yourself. Wait, you cannot.",
                    "source": {
                        "pointer": "/data",
                    },
                }
            )

        if user.followers.filter(pk=request.user.pk).exists():
            raise serializers.ValidationError(
                {
                    "id": "user_already_followed",
                    "detail": "You are already following the user.",
                    "source": {
                        "pointer": "/data",
                    },
                }
            )

        request.user.following.add(user)

        return HttpResponse("", status=204)

    @permission_classes([permissions.IsAuthenticated])
    def unfollow(self, request, *args, **kwargs):
        """
        Unfollow a user.
        """

        user = self.get_object()

        if user == request.user:
            raise serializers.ValidationError(
                {
                    "id": "self_follow_forbidden",
                    "detail": "You cannot unfollow yourself.",
                    "source": {
                        "pointer": "/data",
                    },
                }
            )

        if not user.followers.filter(pk=request.user.pk).exists():
            raise serializers.ValidationError(
                {
                    "id": "user_not_followed",
                    "detail": "You are not following this user.",
                    "source": {
                        "pointer": "/data",
                    },
                }
            )

        request.user.following.remove(user)

        return HttpResponse("", status=204)


@method_decorator(ratelimit(group="api", key="ip", rate="5/m"), name="put")
class UserAvatarUploadView(APIView):
    """
    This view handles the user avatar image upload.
    """

    parser_classes = [parsers.MultiPartParser]
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        """
        Handle the file upload.
        """

        file_bytes = request.data["file"].file

        # Prevent from uploading files > 2 MB size
        if file_bytes.getbuffer().nbytes > 2097152:
            raise serializers.ValidationError(
                detail="The file is too large. What were you uploading? The max file size is 2 MB!",
                code="file_size_exceeded",
            )

        image = Image.open(file_bytes)
        image.verify()

        if image.format.lower() not in ["jpeg", "png", "webp", "jfif", "avif", "bmp"]:
            raise serializers.ValidationError(
                detail="The uploaded image's format is not supported. Is it even an image?",
                code="invalid_file_format",
            )

        request.user.avatar_image = File(file_bytes, name="avatar.webp")
        request.user.save()

        image.close()

        return HttpResponse("", status=204)


@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="get")
class UserRelationshipsView(views.RelationshipView):
    queryset = User.objects.all()

    def get_object(self):
        if (self.request.user.is_authenticated and self.kwargs.get("pk") == "@me") or (
            isinstance(self.request.user, User)
            and self.kwargs.get("pk") == str(self.request.user.id)
        ):
            return self.request.user
        elif not self.request.user.is_authenticated and self.kwargs.get("pk") == "@me":
            raise exceptions.NotAuthenticated()
        else:
            return User.objects.get(pk=self.kwargs.get("pk"))

    def get(self, request, pk, related_field, *args, **kwargs):
        """
        Verifies that the request is not trying to access private
        endpoints.
        """
        if related_field in ["saved-images"]:
            if not request.user.is_authenticated:
                raise exceptions.NotAuthenticated()
            elif str(request.user.pk) != str(pk):
                raise serializers.ValidationError(
                    detail="You cannot see this information.", code="forbidden"
                )

        return super().get(request, pk=pk, related_field=related_field, *args, **kwargs)


@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="list")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="retrieve")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="retrieve_related")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="update")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="delete")
@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="create")
class DomainView(views.ModelViewSet):
    """
    CRUD for domains.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DomainSerializer
    select_for_includes = {"user": ["user"]}

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Domain.objects.filter()
        return Domain.objects.filter(user=self.request.user)

    def delete(self, request, pk):
        """
        Delete a domain.
        """

        domain = get_object_or_404(self.get_queryset().select_related("user"), pk=pk)

        if not request.user.is_superuser:
            if request.user != domain.user:
                raise serializers.ValidationError(
                    detail="You cannot delete an domain that you do not own.",
                    code="cannot_delete_unowned_domain",
                )

        domain.delete()

        return Response(data="", status=204)


@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="get")
class DomainRelationshipsView(views.RelationshipView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DomainSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Domain.objects.all()
        return Domain.objects.filter(user=self.request.user)


@method_decorator(ratelimit(group="api", key="ip", rate="3/s"), name="post")
class AuthorizationWithCaptchaView(AuthorizationView):
    
    def post(self, request, *args, **kwargs):
        """
        Validate the ReCaptcha challenge.
        """

        if not validate_recaptcha(request):
            return self.get(request, *args, **kwargs)

        return super().post(request, *args, **kwargs)
