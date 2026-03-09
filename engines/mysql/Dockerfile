# MySQL 9.0.1 for ScratchBird Benchmarks
# Optimized for testing with benchmark database pre-configured

FROM ubuntu:22.04

LABEL maintainer="ScratchBird Benchmarks"
LABEL description="MySQL 9.0.1 benchmark engine"

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# MySQL version and configuration
ENV MYSQL_VERSION=9.0.1
ENV MYSQL_ROOT_PASSWORD=rootpassword
ENV MYSQL_DATABASE=benchmark
ENV MYSQL_USER=benchmark
ENV MYSQL_PASSWORD=benchmark

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    netcat \
    libaio1 \
    libnuma1 \
    libtinfo5 \
    && rm -rf /var/lib/apt/lists/*

# Download and install MySQL 9.0.1
# Using MySQL APT repository for easier installation
RUN wget -q https://dev.mysql.com/get/mysql-apt-config_0.8.29-1_all.deb -O /tmp/mysql-apt.deb \
    && dpkg -i /tmp/mysql-apt.deb || true \
    && apt-get update \
    && apt-get install -y mysql-server mysql-client \
    && rm -rf /var/lib/apt/lists/* /tmp/mysql-apt.deb

# MySQL directories
RUN mkdir -p /var/lib/mysql /var/run/mysqld \
    && chown -R mysql:mysql /var/lib/mysql /var/run/mysqld

# Copy configuration
COPY my.cnf /etc/mysql/my.cnf
COPY collect-version.sh /usr/local/bin/collect-version.sh
RUN chmod +x /usr/local/bin/collect-version.sh

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose MySQL port
EXPOSE 3306

# Health check
HEALTHCHECK --interval=5s --timeout=3s --start-period=30s --retries=10 \
    CMD /usr/local/bin/collect-version.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["mysqld"]
