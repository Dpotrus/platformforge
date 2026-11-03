FROM python:3.13-slim

WORKDIR /app

COPY server.py .

USER 65532:65532

EXPOSE 8080

CMD ["python", "-u", "server.py"]
