# 1. Usar una imagen oficial de Python como base
FROM python:3.12

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Copiar el archivo de dependencias al contenedor
COPY . /app

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg && apt-get install -y --no-install-recommends libsox-dev

# 4. Instalar las dependencias
RUN pip install --no-cache-dir -r /app/requirements.txt

# 6. Exponer el puerto 80 para que la aplicación sea accesible
EXPOSE 8000

# 7. Comando para ejecutar la aplicación cuando se inicie el contenedor
CMD ["uvicorn", "main:app", "--reload", "--log-level", "debug", "--host", "0.0.0.0", "--port", "8000"]
#CMD ["hypercorn", "main:app", "--reload", "--log-level", "debug", "-b", "0.0.0.0:8000"]