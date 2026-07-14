#!/bin/bash

# Check if the certificates already exist and generate them if they do not
if [ ! -f "./cert.pem" ] || [ ! -f "./key.pem" ]; then
    echo "Generating SSL certificates..."
    openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/C=US/ST=Denial/L=Springfield/O=Dis/CN=www.example.com"
    echo "SSL certificates generated."
else
    echo "SSL certificates already exist."
fi
