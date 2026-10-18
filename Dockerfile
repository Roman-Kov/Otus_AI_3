FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY main.py ./

RUN pip install --no-cache-dir .

EXPOSE 8001

CMD ["uvicorn", "api_agent.api.app:app", "--host", "0.0.0.0", "--port", "8001"]
