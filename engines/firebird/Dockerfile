# FirebirdSQL Benchmark Container
# Uses official Firebird image with benchmark schema pre-loaded

FROM jacobalberty/firebird:v4.0.4

LABEL maintainer="ScratchBird Benchmarks"
LABEL description="FirebirdSQL 4.0.4 for comparative benchmarking"

# Install additional tools for benchmarking
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    procps \
    sysstat \
    && rm -rf /var/lib/apt/lists/*

# Create benchmark user and database
ENV FIREBIRD_DATABASE=benchmark.fdb
ENV FIREBIRD_USER=benchmark
ENV FIREBIRD_PASSWORD=benchmark
ENV FIREBIRD_ROOT_PASSWORD=masterkey

# Copy initialization scripts
COPY init/ /docker-entrypoint-initdb.d/
COPY config/firebird.conf /firebird/etc/firebird.conf

# Version tracking script
COPY scripts/collect-version.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/collect-version.sh

# Benchmark schema will be created on first run
EXPOSE 3050

# Health check
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=3 \
    CMD /usr/local/bin/collect-version.sh > /dev/null 2>&1 || exit 1
