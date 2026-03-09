#!/bin/bash
# Firebird Docker Entrypoint

set -e

# Ensure proper permissions
chown -R firebird:firebird /firebird/data

# Initialize security database if it doesn't exist
if [ ! -f "$FIREBIRD_HOME/security5.fdb" ]; then
    echo "Initializing Firebird security database..."
    cp "$FIREBIRD_HOME/examples/udr/security5.fdb" "$FIREBIRD_HOME/security5.fdb" 2>/dev/null || true
    chown firebird:firebird "$FIREBIRD_HOME/security5.fdb" 2>/dev/null || true
fi

# Create benchmark user if it doesn't exist
create_benchmark_user() {
    echo "Creating benchmark user..."
    $FIREBIRD_HOME/bin/isql -user SYSDBA -password masterkey security.db <<EOF 2>/dev/null || true
CREATE USER benchmark PASSWORD 'benchmark';
COMMIT;
EOF
}

# Start Firebird in background
echo "Starting Firebird $FB_VERSION..."
$FIREBIRD_HOME/bin/firebird &

# Wait for Firebird to be ready
echo "Waiting for Firebird to be ready..."
for i in {1..30}; do
    if $FIREBIRD_HOME/bin/isql -user SYSDBA -password masterkey -quiet <<EOF 2>/dev/null; then
SELECT 1 FROM rdb\$database;
EOF
        echo "Firebird is ready"
        break
    fi
    sleep 1
done

# Create benchmark user
create_benchmark_user

# Create benchmark database if it doesn't exist
if [ ! -f "/firebird/data/${FIREBIRD_DATABASE}" ]; then
    echo "Creating benchmark database..."
    $FIREBIRD_HOME/bin/isql -user benchmark -password benchmark <<EOF
CREATE DATABASE '/firebird/data/${FIREBIRD_DATABASE}' USER 'benchmark' PASSWORD 'benchmark';
COMMIT;
EOF
    echo "Benchmark database created"
fi

# If command is provided, execute it
if [ "$1" != "firebird" ]; then
    exec "$@"
fi

# Keep Firebird running in foreground
wait
