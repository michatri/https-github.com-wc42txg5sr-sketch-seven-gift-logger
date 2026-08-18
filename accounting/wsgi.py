"""WSGI entry point for gunicorn on the LAN server."""

from accounting.app import create_app

app = create_app()
