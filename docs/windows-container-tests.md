# Running containerised tests from Windows CMD

These helpers assume Docker Desktop is running and the repo root is the current directory.

1. Build and start the stack:
   ```cmd
   docker compose up -d --build
   ```

2. Check container status:
   ```cmd
   docker compose ps
   ```

3. Run the auth-host test suite (pytest is available inside the image):
   ```cmd
   docker compose exec -T auth-host python -m pytest -q
   ```

4. Run the core-api suite:
   ```cmd
   docker compose exec -T core-api pytest -q
   ```

5. When finished:
   ```cmd
   docker compose down
   ```

For Git Bash or PowerShell the commands are the same, but quoting rules may differ for environment overrides.
