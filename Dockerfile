# 1. Imagen base ligera de Python
FROM python:3.11-slim

# 2. Evita que Python escriba archivos .pyc en disco y fuerza el stdout/stderr sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Instalar dependencias del sistema necesarias (si fuera necesario para compilaciones)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiar primero el requirements.txt para aprovechar la caché de capas de Docker
COPY requirements.txt /app/

# 6. Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 7. Copiar el resto del código del proyecto al contenedor
COPY . /app/

# 8. Exponer el puerto donde corre FastAPI (ejemplo: 8000)
EXPOSE 8000

# 9. Comando por defecto para iniciar la aplicación mediante Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]