#!/bin/bash
# Generate TLS certificates for Slurm Heartbeat daemon
# Usage: ./generate_certs.sh [site_name] [output_dir]

set -e

SITE_NAME="${1:-localhost}"
OUTPUT_DIR="${2:-/etc/slurm/heartbeat}"

echo "Generating TLS certificates for site: $SITE_NAME"
echo "Output directory: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate CA key and certificate
echo "Generating CA key and certificate..."
openssl genrsa -out "$OUTPUT_DIR/ca.key" 4096
openssl req -x509 -new -nodes -key "$OUTPUT_DIR/ca.key" \
    -sha256 -days 3650 -out "$OUTPUT_DIR/ca.pem" \
    -subj "/CN=EFP Heartbeat CA/O=EFP/C=EU"

# Generate site key and certificate signing request
echo "Generating site key and CSR..."
openssl genrsa -out "$OUTPUT_DIR/site.key" 4096
openssl req -new -key "$OUTPUT_DIR/site.key" -out "$OUTPUT_DIR/site.csr" \
    -subj "/CN=$SITE_NAME/O=EFP/C=EU"

# Create extensions file for site certificate
cat > "$OUTPUT_DIR/site.ext" << EOF
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = DNS:$SITE_NAME, IP:127.0.0.1
EOF

# Sign site certificate with CA
echo "Signing site certificate..."
openssl x509 -req -in "$OUTPUT_DIR/site.csr" \
    -CA "$OUTPUT_DIR/ca.pem" -CAkey "$OUTPUT_DIR/ca.key" -CAcreateserial \
    -out "$OUTPUT_DIR/site.pem" -days 365 -sha256 \
    -extfile "$OUTPUT_DIR/site.ext"

# Copy to standard names
cp "$OUTPUT_DIR/site.pem" "$OUTPUT_DIR/cert.pem"
cp "$OUTPUT_DIR/site.key" "$OUTPUT_DIR/key.pem"

# Set permissions
chmod 600 "$OUTPUT_DIR/key.pem"
chmod 644 "$OUTPUT_DIR/cert.pem" "$OUTPUT_DIR/ca.pem"

# Clean up temporary files
rm -f "$OUTPUT_DIR/site.csr" "$OUTPUT_DIR/site.ext" "$OUTPUT_DIR/ca.srl"

echo ""
echo "Certificates generated successfully!"
echo ""
echo "Files created:"
echo "  - $OUTPUT_DIR/ca.pem (CA certificate)"
echo "  - $OUTPUT_DIR/cert.pem (Site certificate)"
echo "  - $OUTPUT_DIR/key.pem (Site private key)"
echo ""
echo "To use these certificates, configure:"
echo "  tls:"
echo "    cert_file: $OUTPUT_DIR/cert.pem"
echo "    key_file: $OUTPUT_DIR/key.pem"
echo "    ca_file: $OUTPUT_DIR/ca.pem"
echo ""
