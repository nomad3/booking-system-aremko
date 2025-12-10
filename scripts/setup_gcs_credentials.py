#!/usr/bin/env python
"""
Script para configurar las credenciales de Google Cloud Storage
desde una variable de entorno en formato JSON.

Se ejecuta automáticamente al iniciar el servidor en Render.
"""

import os
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def setup_gcs_credentials():
    """
    Crea el archivo de credenciales de GCS desde la variable de entorno.
    Se ejecuta al inicio del servidor en Render.
    """
    credentials_json = os.getenv('GCS_CREDENTIALS_JSON')

    if not credentials_json:
        logger.warning("GCS_CREDENTIALS_JSON no configurado - usando almacenamiento local")
        return False

    try:
        # Parsear el JSON para validarlo
        credentials_data = json.loads(credentials_json)

        # Crear el archivo de credenciales en /tmp (escribible en Render)
        credentials_path = Path('/tmp/gcs-credentials.json')
        with open(credentials_path, 'w') as f:
            json.dump(credentials_data, f, indent=2)

        # Configurar la variable de entorno para que Google Cloud la encuentre
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(credentials_path)

        logger.info(f"Credenciales de GCS configuradas exitosamente")
        logger.info(f"  Proyecto: {credentials_data.get('project_id')}")
        logger.info(f"  Cuenta: {credentials_data.get('client_email')}")

        print(f"✅ Credenciales de GCS configuradas")
        print(f"   Proyecto: {credentials_data.get('project_id')}")
        print(f"   Cuenta de servicio: {credentials_data.get('client_email', '').split('@')[0]}")

        return True

    except json.JSONDecodeError as e:
        error_msg = f"Error al parsear GCS_CREDENTIALS_JSON: {e}"
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        return False
    except Exception as e:
        error_msg = f"Error configurando credenciales GCS: {e}"
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        return False

if __name__ == "__main__":
    # Si se ejecuta directamente, configurar las credenciales
    import sys
    success = setup_gcs_credentials()
    sys.exit(0 if success else 1)