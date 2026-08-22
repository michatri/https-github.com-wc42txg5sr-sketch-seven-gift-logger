FROM python:3.12-slim

WORKDIR /opt/catholic-id
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/opt/catholic-id

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

RUN mkdir -p /opt/catholic-id/app/uploads/photos /opt/catholic-id/app/data

EXPOSE 8222
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8222"]
