#!/bin/bash
set -e
 
echo "Alustan andmete importi..."

echo "1/3 - Loading EMTAK..."
python scripts/03_load_emtak.py 

echo "2/3 - Loading Statistikaamet..."
python scripts/01_load_statistikaamet.py
 
echo "3/3 - Loading Äriregister yldandmed..."
python scripts/02_01_load_ariregister_yldandmed.py
 

echo "Andmed imporditud!"