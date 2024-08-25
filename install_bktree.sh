#!/bin/bash
set -e

# Check if the bktree extension is already installed
if psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_available_extensions WHERE name='bktree'" | grep -q 1; then
    echo "Extension 'bktree' is already available."
else
    echo "Extension 'bktree' not found. Installing..."

    # Install necessary packages
    apt-get update && apt-get install -y \
        git \
        build-essential \
        postgresql-server-dev-all

    # Clone the extension's repository
    git clone https://github.com/fake-name/pg-spgist_hamming.git /tmp/pg-spgist_hamming

    # Navigate to the bktree directory and build/install the extension
    cd /tmp/pg-spgist_hamming/bktree
    make
    make install

    # Clean up
    rm -rf /tmp/pg-spgist_hamming
fi
