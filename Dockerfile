FROM python:3.12-slim AS builder
ARG UV_VERSION=0.11.28
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev && \
    uv build --wheel --out-dir /wheels

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system app && useradd --system --gid app --home /home/app app && \
    mkdir -p /home/app && chown app:app /home/app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

USER app
EXPOSE 9000 9100
ENTRYPOINT ["ocpp-bench"]
CMD ["csms", "--host", "0.0.0.0", "--port", "9000", "--admin-port", "9100"]
