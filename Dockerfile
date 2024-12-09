FROM python:3.9-slim-buster  # Use a slimmer base image

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt --no-cache-dir  # Install without caching

COPY . .

CMD ["python", "bot.py"]
