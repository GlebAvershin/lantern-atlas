FROM python:3.12-slim-bookworm AS build
RUN pip install --no-cache-dir uv==0.13.6
WORKDIR /studio
COPY platform ./platform
COPY game ./game
RUN uv sync --project platform --locked --no-dev && \
    if test -f game/analysis/uv.lock; then uv sync --project game/analysis --locked --no-dev; fi && \
    if test -f game/oracle.cpp; then apt-get update && apt-get install -y --no-install-recommends g++ && \
        g++ -std=c++17 -O2 game/oracle.cpp -o /studio/oracle; fi

FROM python:3.12-slim-bookworm
WORKDIR /studio
COPY --from=build /studio /studio
ENV ATLAS_ORACLE=/studio/oracle PYTHONDONTWRITEBYTECODE=1
USER 65534:65534
CMD ["/studio/platform/.venv/bin/uvicorn","gateway:app","--app-dir","/studio/platform","--host","0.0.0.0","--port","8080"]
