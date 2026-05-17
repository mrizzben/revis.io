#!/bin/bash
# Setup MinIO CORS configuration for ArchiDrive
# This script configures CORS on the MinIO server to allow browser access to presigned URLs

set -e

MINIO_ENDPOINT="http://localhost:9000"
MINIO_CONSOLE="http://localhost:9001"
MINIO_ROOT_USER="minioadmin"
MINIO_ROOT_PASSWORD="minioadmin"
BUCKET_NAME="archidrive"
CORS_CONFIG_FILE="$(dirname "$0")/minio-cors-config.json"

echo "=========================================="
echo "MinIO CORS Configuration Setup"
echo "=========================================="
echo ""

# Check if MinIO is running
echo "Checking if MinIO is running at ${MINIO_ENDPOINT}..."
if ! curl -s -f "${MINIO_ENDPOINT}/minio/health/live" > /dev/null 2>&1; then
    echo "ERROR: MinIO is not running at ${MINIO_ENDPOINT}"
    echo "Please start MinIO first using: docker compose up -d minio"
    exit 1
fi
echo "MinIO is running!"
echo ""

# Check if mc (MinIO Client) is installed
if ! command -v mc &> /dev/null; then
    echo "MinIO Client (mc) is not installed."
    echo ""
    echo "Installing mc..."
    echo ""
    
    # Detect OS and install mc
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install minio/stable/mc
        else
            echo "Please install Homebrew first or download mc manually from:"
            echo "https://dl.min.io/client/mc/release/darwin-amd64/mc"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        curl https://dl.min.io/client/mc/release/linux-amd64/mc \
          --create-dirs \
          -o $HOME/minio-binaries/mc
        chmod +x $HOME/minio-binaries/mc
        export PATH=$PATH:$HOME/minio-binaries/
    else
        echo "Please download mc manually from: https://min.io/docs/minio/linux/reference/minio-mc.html"
        exit 1
    fi
fi

echo "Using MinIO Client: $(which mc)"
echo ""

# Configure mc alias
echo "Configuring MinIO client alias..."
mc alias set archidrive "${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" --api s3v4

# Check if bucket exists, create if not
echo "Checking if bucket '${BUCKET_NAME}' exists..."
if ! mc ls archidrive/${BUCKET_NAME} > /dev/null 2>&1; then
    echo "Creating bucket '${BUCKET_NAME}'..."
    mc mb archidrive/${BUCKET_NAME}
    echo "Bucket created!"
else
    echo "Bucket '${BUCKET_NAME}' already exists."
fi
echo ""

# Apply CORS configuration
echo "Applying CORS configuration..."
echo "Using config file: ${CORS_CONFIG_FILE}"
echo ""

if [ ! -f "${CORS_CONFIG_FILE}" ]; then
    echo "ERROR: CORS config file not found: ${CORS_CONFIG_FILE}"
    exit 1
fi

# Apply CORS using mc admin config
mc admin config set archidrive api cors="$(cat ${CORS_CONFIG_FILE})"

echo ""
echo "Restarting MinIO to apply CORS configuration..."
# Note: In Docker, we need to restart the container
docker compose restart minio

echo ""
echo "=========================================="
echo "CORS Configuration Complete!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Allowed Origins: http://localhost:5173, http://localhost:9000, http://localhost:8000"
echo "  - Allowed Methods: GET, PUT, POST, DELETE, HEAD, OPTIONS"
echo "  - Allowed Headers: *"
echo "  - Max Age: 3000 seconds"
echo ""
echo "Next steps:"
echo "  1. Wait for MinIO to be healthy (about 5-10 seconds)"
echo "  2. Test image access in the browser"
echo ""
echo "Alternative: You can also configure CORS via the MinIO Console at:"
echo "  ${MINIO_CONSOLE}"
echo "  Login: ${MINIO_ROOT_USER} / ${MINIO_ROOT_PASSWORD}"
echo ""
