#!/bin/bash
# Health check and version collection script for MySQL

set -e

# Check if MySQL is running
if ! pgrep -x "mysqld" > /dev/null; then
    echo "MySQL process not running"
    exit 1
fi

# Wait for MySQL to be ready
for i in {1..30}; do
    if mysqladmin -u root -p"${MYSQL_ROOT_PASSWORD}" ping --silent 2>/dev/null; then
        break
    fi
    sleep 1
done

# Get version info
VERSION=$(mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -e "SELECT VERSION();" --silent --skip-column-names 2>/dev/null)

if [ -z "$VERSION" ]; then
    echo "Failed to get MySQL version"
    exit 1
fi

# Write version info to benchmark results
mkdir -p /benchmark-results
cat > /benchmark-results/mysql-version.json <<EOF
{
    "engine": "mysql",
    "version": "$VERSION",
    "timestamp": "$(date -Iseconds)",
    "database": "${MYSQL_DATABASE}",
    "status": "healthy"
}
EOF

echo "MySQL $VERSION - Healthy"
exit 0
