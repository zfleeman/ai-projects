FROM python:3.13-alpine
RUN apk add --no-cache ffmpeg git
RUN mkdir -p /app
WORKDIR /app
COPY requirements.txt .
ENV TZ="America/Denver"
RUN pip install -r requirements.txt
ENTRYPOINT ["python", "src/app.py"]