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


class ChangePasswordSerializer(serializers.Serializer):
    """
    Valida los datos necesarios para cambiar la contraseña propia.

    @version 1.0
    @author Agustin
    """

    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        """
        Confirma que la nueva contraseña fue ingresada dos veces de igual forma.

        @version 1.0
        @param attrs Datos validados por campo.
        @author Agustin
        """
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": ["Las contraseñas no coinciden."]}
            )
        return attrs


class SystemAdminSerializer(serializers.Serializer):
    """
    Valida el cambio explícito de administración global.

    @version 1.0
    @author Agustin
    """

    is_system_admin = serializers.BooleanField()
