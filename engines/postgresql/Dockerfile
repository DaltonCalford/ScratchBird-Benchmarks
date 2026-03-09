# PostgreSQL Benchmark Container
# Uses official PostgreSQL 16 image with benchmark schema pre-loaded

FROM postgres:16.1

LABEL maintainer="ScratchBird Benchmarks"
LABEL description="PostgreSQL 16.1 for comparative benchmarking"

# Install additional tools for benchmarking
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    procps \
    sysstat \
    && rm -rf /var/lib/apt/lists/*

# Environment variables
ENV POSTGRES_USER=benchmark
ENV POSTGRES_PASSWORD=benchmark
ENV POSTGRES_DB=benchmark

# Copy configuration and init scripts
COPY config/postgresql.conf /etc/postgresql/postgresql.conf
COPY init/ /docker-entrypoint-initdb.d/

# Version tracking script
COPY scripts/collect-version.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/collect-version.sh

EXPOSE 5432

# Health check
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
    CMD /usr/local/bin/collect-version.sh > /dev/null 2>&1 || exit 1
