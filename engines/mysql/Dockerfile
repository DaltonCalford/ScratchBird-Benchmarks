# MySQL Benchmark Container
# Uses official MySQL 9.0 image with benchmark schema pre-loaded

FROM mysql:9.0.1

LABEL maintainer="ScratchBird Benchmarks"
LABEL description="MySQL 9.0.1 for comparative benchmarking"

# Install additional tools for benchmarking
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    procps \
    sysstat \
    && rm -rf /var/lib/apt/lists/*

# Environment variables
ENV MYSQL_ROOT_PASSWORD=rootpassword
ENV MYSQL_DATABASE=benchmark
ENV MYSQL_USER=benchmark
ENV MYSQL_PASSWORD=benchmark

# Copy configuration and init scripts
COPY config/my.cnf /etc/mysql/conf.d/benchmark.cnf
COPY init/ /docker-entrypoint-initdb.d/

# Version tracking script
COPY scripts/collect-version.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/collect-version.sh

EXPOSE 3306

# Health check
HEALTHCHECK --interval=5s --timeout=3s --start-period=30s --retries=3 \
    CMD /usr/local/bin/collect-version.sh > /dev/null 2>&1 || exit 1
