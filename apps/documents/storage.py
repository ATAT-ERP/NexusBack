from django.conf import settings
from supabase import create_client


storage_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
