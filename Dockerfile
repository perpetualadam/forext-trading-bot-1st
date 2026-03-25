# Forex bot + FastAPI dashboard
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY forex_bot ./forex_bot
COPY main.py .

EXPOSE 8000

# Single worker: bot loop runs in-process via FastAPI lifespan (do not scale replicas blindly).
CMD ["uvicorn", "forex_bot.app:app", "--host", "0.0.0.0", "--port", "8000"]
