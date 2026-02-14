#!/bin/bash
set -euo pipefail

# --- Install Docker ---
dnf install -y docker
systemctl enable docker
systemctl start docker

# --- Authenticate to ECR ---
aws ecr get-login-password --region ${aws_region} \
  | docker login --username AWS --password-stdin ${aws_account_id}.dkr.ecr.${aws_region}.amazonaws.com

# --- Pull and run the app ---
docker pull ${ecr_repo_url}:latest || true

docker run -d \
  --name weather-app \
  --restart unless-stopped \
  -p 80:80 \
  -v smhi_cache:/app/backend/cache \
  ${ecr_repo_url}:latest
