FROM localhost:5001/argus/python:3.12-alpine

WORKDIR /app
COPY server.py /app/server.py

USER nobody
EXPOSE 8080

ENTRYPOINT ["python", "-u", "/app/server.py"]
