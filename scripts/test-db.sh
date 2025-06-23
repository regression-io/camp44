#!/bin/bash
set -eo pipefail

# Helper script to run pgTAP tenant isolation tests
# Spins up a temporary Postgres container, applies migrations,
# runs the tenant isolation tests, and reports status

POSTGRES_CONTAINER="camp44-pgtap-test"
POSTGRES_PASSWORD="securepassword"
POSTGRES_USER="postgres"
POSTGRES_DB="camp44_test"
POSTGRES_PORT="5433"  # Non-standard port to avoid conflicts

echo "Starting temporary Postgres container for pgTAP tests..."
docker run --rm --name $POSTGRES_CONTAINER \
  -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
  -e POSTGRES_USER=$POSTGRES_USER \
  -e POSTGRES_DB=$POSTGRES_DB \
  -p $POSTGRES_PORT:5432 \
  -d postgres:15-alpine

# Wait for Postgres to be ready
echo "Waiting for Postgres to be ready..."
until docker exec $POSTGRES_CONTAINER pg_isready -U $POSTGRES_USER -d $POSTGRES_DB; do
  echo "Postgres is not ready - sleeping for 1 second"
  sleep 1
done

# Install pgTAP
echo "Installing pgTAP..."
docker exec $POSTGRES_CONTAINER bash -c "
  apk add --no-cache git make gcc postgresql-dev musl-dev perl perl-dev perl-dbi perl-dbd-pg perl-test-harness
  cd /tmp && git clone https://github.com/theory/pgtap.git && cd pgtap
  make && make install
  echo 'CREATE EXTENSION pgtap;' | psql -U $POSTGRES_USER -d $POSTGRES_DB
"

# Run alembic migrations against the test database
echo "Running Alembic migrations..."
export SQLALCHEMY_DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB"
alembic upgrade head

# Run pgTAP tests
echo "Running pgTAP tenant isolation tests..."
EXIT_CODE=0
for test_file in tests/pgtap/*.sql; do
  echo "Running $test_file..."
  if ! cat $test_file | docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB; then
    echo "Test $test_file failed"
    EXIT_CODE=1
  fi
done

# Cleanup
echo "Cleaning up..."
docker stop $POSTGRES_CONTAINER

exit $EXIT_CODE
