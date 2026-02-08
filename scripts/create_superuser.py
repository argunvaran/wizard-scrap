from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = 'admin'
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Yakut18!')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, 'admin@example.com', password)
    print(f"Superuser '{username}' created.")
else:
    print(f"Superuser '{username}' already exists.")
