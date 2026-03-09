#!/bin/bash
# MySQL Docker Entrypoint

set -e

# Initialize MySQL data directory if needed
if [ ! -d "/var/lib/mysql/mysql" ]; then
    echo "Initializing MySQL data directory..."
    mysqld --initialize-insecure --user=mysql
    
    # Start MySQL temporarily to set up users
    echo "Starting MySQL for initial setup..."
    mysqld --skip-networking --socket=/var/run/mysqld/mysqld.sock &
    
    # Wait for MySQL to be ready
    for i in {1..60}; do
        if mysqladmin -u root --silent ping 2>/dev/null; then
            break
        fi
        sleep 1
    done
    
    # Set root password and create benchmark user
    echo "Setting up MySQL users and database..."
    mysql -u root <<EOF
ALTER USER 'root'@'localhost' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}';
CREATE DATABASE IF NOT EXISTS ${MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON ${MYSQL_DATABASE}.* TO '${MYSQL_USER}'@'%';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EOF
    
    # Shutdown temporary MySQL
    mysqladmin -u root -p"${MYSQL_ROOT_PASSWORD}" shutdown
    
    echo "MySQL initialization complete"
fi

# Ensure proper permissions
chown -R mysql:mysql /var/lib/mysql /var/run/mysqld

# If command is provided, execute it
if [ "$1" != "mysqld" ]; then
    exec "$@"
fi

# Start MySQL in foreground
echo "Starting MySQL ${MYSQL_VERSION}..."
exec mysqld --user=mysql
