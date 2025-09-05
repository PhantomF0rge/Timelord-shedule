from app import create_app
application = create_app()  # for WSGI servers like gunicorn: `--bind :8000 wsgi:application`
