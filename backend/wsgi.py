"""WSGI entry point for PythonAnywhere.

PythonAnywhere serves WSGI apps; FastAPI is ASGI, so a2wsgi bridges the two.
PythonAnywhere's own WSGI config file should add this folder to sys.path and
then do:  from wsgi import application
"""

from a2wsgi import ASGIMiddleware

from app.main import app

application = ASGIMiddleware(app)
