#!/bin/sh

# Wait for database if using postgres
if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Apply database migrations
# Apply database migrations
python manage.py migrate --noinput

# Create Superuser (if not exists)
echo "Ensuring superuser exists..."
python manage.py shell < /app/scripts/create_superuser.py

# Collect static files
python manage.py collectstatic --noinput

# Start server
# gunicorn league_system.wsgi:application --bind 0.0.0.0:8000
exec "$@"
