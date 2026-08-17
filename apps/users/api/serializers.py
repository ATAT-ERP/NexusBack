from rest_framework import serializers

from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "avatar_path",
            "is_active",
            "is_system_admin",
        )
        read_only_fields = ("id", "email", "is_active", "is_system_admin")


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class SystemAdminSerializer(serializers.Serializer):
    """
    Valida el cambio explícito de administración global.

    @version 1.0
    @author Agustin
    """

    is_system_admin = serializers.BooleanField()
