FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

ENV ITKB_PROGRAM_PATH=/app/PROGRAM.md
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["kb", "serve", "--host", "0.0.0.0", "--port", "8000"]
