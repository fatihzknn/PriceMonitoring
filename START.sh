#!/bin/bash
cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "Python bulunamadi! Once SETUP.sh calistirin."
    read -p "Enter'a basin..."
    exit 1
fi

open http://localhost:8080 2>/dev/null || xdg-open http://localhost:8080 2>/dev/null &
python3 app.py
