FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-fra \
    poppler-utils \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download fr_core_news_md

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]