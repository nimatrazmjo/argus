FROM localhost:5001/argus/python:3.12-alpine

RUN pip install --no-cache-dir flask

WORKDIR /app
COPY app.py /app/app.py

USER nobody
EXPOSE 8080

ENTRYPOINT ["python", "-u", "/app/app.py"]
