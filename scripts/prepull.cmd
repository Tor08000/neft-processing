@echo off
echo Pre-pulling base images to avoid network failures during compose builds...

docker pull postgres:16
docker pull redis:7
docker pull nginx:1.27-alpine
docker pull python:3.11-slim
docker pull node:20-alpine

echo Done.
