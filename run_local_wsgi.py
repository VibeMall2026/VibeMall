import os
from wsgiref.simple_server import make_server

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VibeMall.settings')

import django
from django.core.wsgi import get_wsgi_application


def main() -> None:
    django.setup()
    app = get_wsgi_application()
    host, port = '127.0.0.1', 8000
    httpd = make_server(host, port, app)
    print(f'WSGI server listening on http://{host}:{port}', flush=True)
    httpd.serve_forever()


if __name__ == '__main__':
    main()
