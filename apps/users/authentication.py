from django.conf import settings
from supabase import create_client


supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def register(email, password):
    """
    Registra un usuario mediante Supabase Auth.

    @version 1.0
    @param email Correo electrónico utilizado para crear la cuenta.
    @param password Contraseña utilizada para crear la cuenta.
    @author Agustin
    """
    return supabase.auth.sign_up({"email": email, "password": password})


def login(email, password):
    """
    Inicia sesión mediante Supabase Auth.

    @version 1.0
    @param email Correo electrónico de la cuenta.
    @param password Contraseña de la cuenta.
    @author Agustin
    """
    return supabase.auth.sign_in_with_password({"email": email, "password": password})
