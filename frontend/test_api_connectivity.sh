#!/bin/bash

echo "Testing API Connectivity"
echo "========================"

echo -e "\n1. Testing local backend directly:"
curl -s http://localhost:8000/api/health | jq . || echo "Failed"

echo -e "\n2. Testing through domain:"
curl -s https://your-domain.com/api/health | jq . || echo "Failed"

echo -e "\n3. Testing auth providers locally:"
curl -s http://localhost:8000/api/auth/providers | jq . || echo "Failed"

echo -e "\n4. Testing auth providers through domain:"
curl -s https://your-domain.com/api/auth/providers | jq . || echo "Failed"

echo -e "\n5. Checking domain response headers:"
curl -I https://your-domain.com/api/health 2>&1 | grep -E "(HTTP|server:|cf-ray:)"

echo -e "\n6. Testing from within backend container:"
docker exec gaia-backend-gpu curl -s http://localhost:8000/api/health | jq . || echo "Failed"

echo -e "\nIf tests 1, 3, and 6 work but 2 and 4 fail, the Cloudflare tunnel API route needs to be updated."
echo "The API route should point to 'localhost:8000' or 'http://gaia-backend-gpu:8000'"