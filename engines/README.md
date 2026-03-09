# Database Engine Docker Images

This directory contains Docker images for the three database engines used in ScratchBird benchmarks.

## Engines

| Engine | Version | Port | Database | User | Password |
|--------|---------|------|----------|------|----------|
| Firebird | 5.0.1 | 3050 | benchmark.fdb | benchmark | benchmark |
| MySQL | 9.0.1 | 3306 | benchmark | benchmark | benchmark |
| PostgreSQL | 16 | 5432 | benchmark | benchmark | benchmark |

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+ (optional, for using docker-compose.yml)
- User must be in the `docker` group or use `sudo`

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Build all engine images
docker-compose build

# Or build specific engine
docker-compose build firebird
docker-compose build mysql
docker-compose build postgresql

# Start all engines
docker-compose up -d firebird mysql postgresql

# Check status
docker-compose ps

# View logs
docker-compose logs -f firebird
```

### Using Docker Directly

#### Firebird

```bash
# Build
cd engines/firebird
docker build -t sb-benchmark-firebird:latest .

# Run
docker run -d \
  --name sb-benchmark-firebird \
  -p 3050:3050 \
  -v firebird_data:/firebird/data \
  -v ./results:/benchmark-results \
  sb-benchmark-firebird:latest

# Check version
docker exec sb-benchmark-firebird /usr/local/bin/collect-version.sh
```

#### MySQL

```bash
# Build
cd engines/mysql
docker build -t sb-benchmark-mysql:latest .

# Run
docker run -d \
  --name sb-benchmark-mysql \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=rootpassword \
  -e MYSQL_DATABASE=benchmark \
  -e MYSQL_USER=benchmark \
  -e MYSQL_PASSWORD=benchmark \
  -v mysql_data:/var/lib/mysql \
  -v ./results:/benchmark-results \
  sb-benchmark-mysql:latest

# Check version
docker exec sb-benchmark-mysql /usr/local/bin/collect-version.sh
```

#### PostgreSQL

```bash
# Build
cd engines/postgresql
docker build -t sb-benchmark-postgresql:latest .

# Run
docker run -d \
  --name sb-benchmark-postgresql \
  -p 5432:5432 \
  -e POSTGRES_USER=benchmark \
  -e POSTGRES_PASSWORD=benchmark \
  -e POSTGRES_DB=benchmark \
  -v postgres_data:/var/lib/postgresql/data \
  -v ./results:/benchmark-results \
  sb-benchmark-postgresql:latest

# Check version
docker exec sb-benchmark-postgresql /usr/local/bin/collect-version.sh
```

## Engine Details

### Firebird 5.0.1

- **Base**: Ubuntu 22.04
- **Installation**: Official Firebird 5.0.1 tarball from GitHub releases
- **Configuration**: `firebird.conf`
- **Features**:
  - Pre-configured benchmark database
  - Legacy and SRP authentication enabled
  - Health check script for version collection

### MySQL 9.0.1

- **Base**: Ubuntu 22.04
- **Installation**: MySQL APT repository
- **Configuration**: `my.cnf`
- **Features**:
  - InnoDB optimized settings
  - Binary logging disabled for benchmark performance
  - UTF8MB4 character set

### PostgreSQL 16

- **Base**: Ubuntu 22.04
- **Installation**: Official PostgreSQL APT repository
- **Configuration**: `postgresql.conf`, `pg_hba.conf`
- **Features**:
  - Performance schema enabled
  - Docker network access configured
  - Benchmark user with superuser privileges

## Troubleshooting

### Permission Denied

If you get permission errors, either:

1. Add your user to the docker group:
   ```bash
   sudo usermod -aG docker $USER
   # Log out and log back in
   ```

2. Use sudo:
   ```bash
   sudo docker-compose build
   ```

### Port Already in Use

If ports 3050, 3306, or 5432 are already in use:

```bash
# Find what's using the port
sudo lsof -i :3050

# Kill the process or use different ports in docker-compose.yml
```

### Build Failures

If builds fail due to network issues:

1. Check internet connectivity
2. Try with `--network host`:
   ```bash
   docker build --network host -t sb-benchmark-firebird .
   ```

3. For Firebird, the tarball URL might need updating. Check:
   https://github.com/FirebirdSQL/firebird/releases

## Health Checks

Each engine includes a `collect-version.sh` script that:
1. Checks if the database process is running
2. Connects to the database
3. Retrieves version information
4. Writes version JSON to `/benchmark-results/`

The docker-compose.yml uses these scripts for health checks.

## Connecting to Engines

### From Host Machine

```bash
# Firebird (using isql-fb or similar)
isql-fb -u benchmark -p benchmark -p 3050 localhost:benchmark.fdb

# MySQL
mysql -u benchmark -pbenchmark -h 127.0.0.1 -P 3306 benchmark

# PostgreSQL
psql -U benchmark -h 127.0.0.1 -p 5432 -d benchmark
```

### From Another Container

```bash
# MySQL from benchmark-runner container
mysql -u benchmark -pbenchmark -h mysql -P 3306 benchmark
```

## Version Information

Each engine writes its version information to `/benchmark-results/` on startup:

- `firebird-version.json`
- `mysql-version.json`
- `postgresql-version.json`

These files are mounted to the host `./results/` directory.

## Customization

### Environment Variables

Edit the `environment` section in `docker-compose.yml`:

```yaml
firebird:
  environment:
    - FIREBIRD_DATABASE=mydb.fdb
    - FIREBIRD_USER=myuser
    - FIREBIRD_PASSWORD=mypass
```

### Configuration Files

Edit the config files in each engine directory:
- `engines/firebird/firebird.conf`
- `engines/mysql/my.cnf`
- `engines/postgresql/postgresql.conf`
- `engines/postgresql/pg_hba.conf`

Then rebuild: `docker-compose build`

## Security Notes

⚠️ **These images are for benchmark/testing only!**

- Weak passwords (`benchmark`/`benchmark`)
- Remote access enabled from any IP
- Root/admin access granted to benchmark user
- No SSL/TLS configured
- Not suitable for production use

## Clean Up

```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes (WARNING: deletes data!)
docker-compose down -v

# Remove images
docker rmi sb-benchmark-firebird sb-benchmark-mysql sb-benchmark-postgresql
```
