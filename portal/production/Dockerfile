FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY portal/production/requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home sevlink
COPY --chown=sevlink:sevlink portal/production/ .
COPY --chown=sevlink:sevlink portal/dist/ ./frontend/
RUN mkdir -p /app/private-attachments /app/private-email-preview && chown sevlink:sevlink /app/private-attachments /app/private-email-preview && chmod 700 /app/private-attachments /app/private-email-preview
USER sevlink
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "45", "--access-logfile", "/dev/null"]
