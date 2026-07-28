#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CERTS_DIR="${ROOT_DIR}/certs"
CERT_FILE="${CERTS_DIR}/cert.pem"
KEY_FILE="${CERTS_DIR}/key.pem"

mkdir -p "${CERTS_DIR}"

if [ ! -f "${CERT_FILE}" ] || [ ! -f "${KEY_FILE}" ]; then
    echo "Generating SSL certificates in ${CERTS_DIR}..."
    openssl req -x509 -newkey rsa:4096 \
        -keyout "${KEY_FILE}" \
        -out "${CERT_FILE}" \
        -days 365 -nodes \
        -subj "/C=US/ST=Denial/L=Springfield/O=Dis/CN=www.example.com"
    echo "SSL certificates generated."
else
    echo "SSL certificates already exist."
fi
