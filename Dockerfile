FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/02-backend:/app/04-langgraph:/app/04-langgraph/agents:/app/04-langgraph/inspecteur:/app/04-langgraph/regisseur:/app/03-agentic-ai/compagnon:/app/05-mcp-server/base-donnees:/app/05-mcp-server/canaux

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.all.txt .
RUN pip install --no-cache-dir -r requirements.all.txt

COPY . .

RUN useradd --create-home --shell /bin/bash sou9na \
 && chown -R sou9na:sou9na /app
USER sou9na

EXPOSE 8000 8100 8101 8102 8103 8201 8204
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS inspecteur
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium nodejs npm poppler-utils tesseract-ocr tesseract-ocr-fra \
 && rm -rf /var/lib/apt/lists/* \
 && npm install --prefix /opt/sou9na-browser --omit=dev playwright-core@1.65.1
ENV DOCUMENT_CHROMIUM_PATH=/usr/bin/chromium \
    NODE_PATH=/opt/sou9na-browser/node_modules
USER sou9na

FROM runtime AS app
