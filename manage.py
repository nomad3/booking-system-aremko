#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "No se pudo importar Django. Asegúrate de que está instalado y disponible en tu PYTHONPATH."
        ) from exc
    execute_from_command_line(sys.argv)
