FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code into the container
COPY . .

# Expose necessary ports (optional for webhooks or APIs)
EXPOSE 8080

# Command to run the bot
CMD ["python", "main.py"]
