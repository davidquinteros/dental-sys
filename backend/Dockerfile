FROM python:3.11-slim

WORKDIR /app

# postgresql-client provides pg_isready, used by entrypoint.sh to wait for the db.
# apt sources are switched to HTTPS first: corporate proxies/firewalls mangle
# plain-HTTP traffic to deb.debian.org ("Bad header line" apt errors, exit 100).
RUN sed -i 's|http://|https://|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
