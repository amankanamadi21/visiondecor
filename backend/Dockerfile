# Dev-oriented image: source is bind-mounted over this at runtime (see
# docker-compose.yml) so code changes hot-reload without a rebuild. Built
# with source baked in anyway so the image is still usable standalone.
FROM python:3.12-slim

# opencv-python (pulled in transitively by ultralytics, alongside the
# -headless variant we asked for) needs libGL at import time even though
# nothing here renders anything visually. python-magic needs libmagic for
# real upload MIME validation (backend/services/image_validation.py).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
# --timeout/--retries: large wheels (torch et al.) occasionally stall
# mid-download inside Docker Desktop's Linux VM even when the same fetch is
# reliable outside a container — retrying beats failing the whole build over
# one flaky connection.
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r backend/requirements.txt

COPY . .

EXPOSE 5000
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
