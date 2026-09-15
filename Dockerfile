FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt && \
    python -m pip check

COPY app.py brain_provider.py candidate_brain.py composition_engine.py experience_memory.py ./
COPY flm_text_provider.py narrative_provider.py server_mechanics.py studio_delta.py ./
COPY context ./context
COPY web ./web

RUN python -m py_compile \
    app.py candidate_brain.py brain_provider.py composition_engine.py \
    experience_memory.py flm_text_provider.py narrative_provider.py \
    server_mechanics.py studio_delta.py

EXPOSE 8080

CMD ["/bin/sh","-c","exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
