# Mock source-system estate: eight FastAPI sub-apps in one process.
# The frozen extracts are not committed (they regenerate byte-identically from seed 42),
# so nothing is copied in — mocks.app's lifespan generates them into EXTRACTS_DIR at
# startup, which is why a fresh clone and a fresh container both just work.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EXTRACTS_DIR=/app/data/extracts

WORKDIR /app

COPY pyproject.toml README.md ./
COPY pipeline/ pipeline/
COPY mocks/ mocks/
COPY evals/ evals/
COPY data/generate_world.py data/generate_world.py

RUN pip install --no-cache-dir .

EXPOSE 8010

CMD ["uvicorn", "mocks.app:app", "--host", "0.0.0.0", "--port", "8010"]
