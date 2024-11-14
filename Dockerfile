# Usar una imagen base de Python
FROM python:3.9-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && \
    apt-get install -y build-essential libpq-dev netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

# Copiar los archivos de requerimientos e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código de la aplicación
COPY . .

# Copiar el script de entrada y asegurarse de que es ejecutable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Exponer el puerto que usará la aplicación (Render asigna el puerto via variable de entorno PORT)
EXPOSE 8000

# Establecer el script de entrada como punto de entrada
ENTRYPOINT ["/entrypoint.sh"]
