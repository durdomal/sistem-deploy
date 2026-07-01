# claude-code-server — headless Claude Code запуск изнутри контейнера.
# На VPS: docker compose -f docker-compose.yml -f docker-compose.cc.yml up -d cc-daemon

FROM node:20-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl python3 python3-pip python3-venv git ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
RUN pip install --no-cache-dir 'fastapi==0.115.6' 'uvicorn[standard]==0.32.1' 'pydantic==2.10.3'

COPY main.py /app/main.py

EXPOSE 8020
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]
