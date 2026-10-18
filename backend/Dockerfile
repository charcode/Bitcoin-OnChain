FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

COPY backend/btc_onchain ./btc_onchain

EXPOSE 8000

CMD ["uvicorn", "btc_onchain.main:app", "--host", "0.0.0.0", "--port", "8000"]
