# Official Postgres 17 Image
# See https://hub.docker.com/_/postgres
FROM postgres:17

# Switch to root temporarily to install dependencies
USER root

# Install dependencies for building pgvector from source.
# Note: As pgvector may not have pre-built packages for Postgres 17 yet,
# we build it from source.
# The postgresql-server-dev-* package provides pg_config and headers for building extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    postgresql-server-dev-17 \
    && rm -rf /var/lib/apt/lists/*

# Configure git to skip SSL verification for this build
RUN git config --global http.sslverify false

# Clone and build pgvector
RUN git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git /usr/src/pgvector
WORKDIR /usr/src/pgvector
RUN make && make install

# Copy initialization SQL
COPY ./init/PGVECTOR_INIT.SQL /docker-entrypoint-initdb.d/

# Clean up build dependencies to reduce image size
RUN apt-get purge -y --auto-remove build-essential git

# Ensure the postgres user owns the necessary directories
RUN chown -R postgres:postgres /var/lib/postgresql/data
RUN chown -R postgres:postgres /docker-entrypoint-initdb.d/

# Switch back to postgres user for security
USER postgres

# Set working directory back to postgres home
WORKDIR /var/lib/postgresql

# Expose the standard PostgreSQL port
EXPOSE 5432
