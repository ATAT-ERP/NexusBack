from rest_framework import serializers

from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Representa el perfil y permite cambiar únicamente los datos personales.

    @version 1.0
    @author Agustin
    """

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
        read_only_fields = (
            "id",
            "email",
            "avatar_path",
            "is_active",
            "is_system_admin",
        )

    def to_internal_value(self, data):
        """
        Rechaza campos ajenos a nombre y apellido en escrituras del perfil.

        @version 1.0
        @author Agustin
        """
        values = super().to_internal_value(data)
        protected_fields = set(data) - {"first_name", "last_name"}
        if protected_fields:
            raise serializers.ValidationError(
                {
                    field: ["Este campo no puede modificarse."]
                    for field in protected_fields
                }
            )
        return values


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
