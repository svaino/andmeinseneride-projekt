FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    requests \
    python-dotenv \
    psycopg2-binary \
    beautifulsoup4 \
    pandas \
    sqlalchemy \
    geopandas

CMD ["bash"]