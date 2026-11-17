FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13-slim
COPY --from=build /app/.venv /app/.venv
ARG VERSION=dev
ENV VERSION=$VERSION PATH="/app/.venv/bin:$PATH"
USER nobody
EXPOSE 8000
CMD ["uvicorn", "hello.main:app", "--host", "0.0.0.0", "--port", "8000"]
