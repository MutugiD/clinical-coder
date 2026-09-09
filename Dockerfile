FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY . .
RUN pip install --no-cache-dir --no-deps --no-build-isolation . && chmod +x scribe
ENTRYPOINT ["./scribe"]
