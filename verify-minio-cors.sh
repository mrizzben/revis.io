#!/bin/bash
# Verify MinIO CORS Configuration for ArchiDrive

echo "=========================================="
echo "MinIO CORS Verification"
echo "=========================================="
echo ""

MINIO_ENDPOINT="http://localhost:9000"
BUCKET_NAME="archidrive"
FRONTEND_ORIGIN="http://localhost:5173"

# Check if MinIO is running
echo "1. Checking if MinIO is running..."
if curl -s -f "${MINIO_ENDPOINT}/minio/health/live" > /dev/null 2>&1; then
    echo "   ✓ MinIO is running at ${MINIO_ENDPOINT}"
else
    echo "   ✗ MinIO is NOT running. Start it with: docker compose up -d minio"
    exit 1
fi
echo ""

# Check if bucket exists
echo "2. Checking if bucket '${BUCKET_NAME}' exists..."
if curl -s -f "${MINIO_ENDPOINT}/${BUCKET_NAME}" > /dev/null 2>&1; then
    echo "   ✓ Bucket '${BUCKET_NAME}' exists"
else
    echo "   ✗ Bucket '${BUCKET_NAME}' not found"
fi
echo ""

# Test CORS preflight request
echo "3. Testing CORS preflight (OPTIONS request)..."
CORS_RESPONSE=$(curl -s -i -X OPTIONS "${MINIO_ENDPOINT}/${BUCKET_NAME}/test-file.txt" \
    -H "Origin: ${FRONTEND_ORIGIN}" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: *" 2>/dev/null)

if echo "$CORS_RESPONSE" | grep -qi "Access-Control-Allow-Origin"; then
    echo "   ✓ CORS is configured! Response includes Access-Control-Allow-Origin"
    echo ""
    echo "   Response headers:"
    echo "$CORS_RESPONSE" | grep -i "Access-Control" | sed 's/^/   /'
else
    echo "   ✗ CORS NOT configured - missing Access-Control-Allow-Origin header"
    echo ""
    echo "   To fix, run: ./setup-minio-cors.sh"
    echo "   Or configure via MinIO Console at http://localhost:9001"
fi
echo ""

# Test with a sample presigned URL (if possible)
echo "4. Testing presigned URL access..."
echo "   (This requires a valid presigned URL from the backend API)"
echo ""
echo "   You can test with:"
echo "   - Upload a file via the frontend"
echo "   - Check if the image displays in the browser"
echo "   - Open browser DevTools > Network tab to see CORS errors"
echo ""

echo "=========================================="
echo "Verification Complete"
echo "=========================================="
