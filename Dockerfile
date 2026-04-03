FROM ghcr.io/benoitc/gunicorn:latest

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --locked

COPY . .

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:80", "run:app"]