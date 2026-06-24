#!/bin/bash
echo "==================================="
echo "Stream Crossing Model Setup"
echo "==================================="

# Stop on first error
set -e

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
# shellcheck disable=SC1091
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Initialize git repository (if not already)
if [ ! -d ".git" ]; then
  echo "Initializing git repository..."
  git init
  git add .
  git commit -m "Initial commit - Stream Crossing Model v1.7"
else
  echo "Git repository already initialized. Skipping git init."
fi

echo
echo "Setup complete!"
echo
echo "Next steps:"
echo "  1. Place your input CSV in data/input/"
echo "  2. Run:"
echo "       source venv/bin/activate"
echo "       python src/model.py --input data/input/your_file.csv"
echo
