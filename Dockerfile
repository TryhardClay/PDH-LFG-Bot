FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt --no-cache-dir

COPY . .

EXPOSE 54321  # Expose the port

# Uninstall and reinstall discord.py
RUN pip uninstall -y discord.py 
RUN pip install discord.py==2.3.2

CMD ["python", "bot.py"]
