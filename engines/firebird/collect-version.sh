#!/bin/bash
# Health check and version collection script for Firebird

set -e

# Check if Firebird is running
if ! pgrep -x "firebird" > /dev/null; then
    echo "Firebird process not running"
    exit 1
fi

# Try to connect and get version info
export ISC_USER=benchmark
export ISC_PASSWORD=benchmark

# Check if benchmark database exists, if not create it
if [ ! -f "/firebird/data/${FIREBIRD_DATABASE}" ]; then
    echo "Creating benchmark database..."
    $FIREBIRD_HOME/bin/isql -user benchmark -password benchmark <<-EOF
        CREATE DATABASE '/firebird/data/${FIREBIRD_DATABASE}' USER 'benchmark' PASSWORD 'benchmark';
        COMMIT;
EOF
fi

# Get version and write to results
VERSION=$($FIREBIRD_HOME/bin/isql -user benchmark -password benchmark -b /firebird/data/${FIREBIRD_DATABASE} <<EOF 2>/dev/null | head -1
SELECT rdb\$get_context('SYSTEM', 'ENGINE_VERSION') FROM rdb\$database;
EOF
)

if [ -z "$VERSION" ]; then
    echo "Failed to get Firebird version"
    exit 1
fi

# Write version info to benchmark results
mkdir -p /benchmark-results
 cat > /benchmark-results/firebird-version.json <<EOF
{
    "engine": "firebird",
    "version": "$VERSION",
    "timestamp": "$(date -Iseconds)",
    "database": "${FIREBIRD_DATABASE}",
    "status": "healthy"
}
EOF

echo "Firebird $VERSION - Healthy"
exit 0
