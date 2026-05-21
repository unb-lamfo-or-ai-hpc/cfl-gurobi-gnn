#!/bin/bash
# Script to download and reconstruct the CFL dataset

# Set variables
VERSION="v1.0.0"
REPO_URL="https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn/releases/download/${VERSION}"

# Array of chunk suffixes (adjust these if you have more parts like ae, af)
PARTS=("aa" "ab" "ac" "ad")
BASE_NAME="CFL_dataset.tar.gz.part"

# Ensure target directory exists
mkdir -p data/raw/MILPBench

echo "Downloading dataset chunks from GitHub Release ${VERSION}..."
for suffix in "${PARTS[@]}"; do
    FILE="${BASE_NAME}${suffix}"
    echo "Fetching ${FILE}..."
    wget -q --show-progress -O "$FILE" "${REPO_URL}/${FILE}"
done

echo "Reconstructing and extracting dataset..."
# Concatenate all parts and pipe directly into tar extraction
cat ${BASE_NAME}* | tar -xzvf - -C data/raw/MILPBench/

echo "Cleaning up downloaded chunks..."
rm ${BASE_NAME}*

echo "✅ Dataset successfully downloaded and extracted to data/raw/MILPBench/CFL"
