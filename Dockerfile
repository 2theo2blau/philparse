FROM python:3.13-slim

COPY src/ /app/src/
COPY frontend/ /app/frontend/
COPY requirements.txt /app/

COPY .env /app/.env

WORKDIR /app

RUN pip install -r requirements.txt

CMD ["python", "src/main.py"]