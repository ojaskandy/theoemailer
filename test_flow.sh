#!/bin/bash

echo "Testing Theo Email Generator..."

# Step 1: Upload CSV and template
echo "Step 1: Uploading CSV and template..."
UPLOAD_RESPONSE=$(curl -s -c cookies.txt -X POST http://localhost:5001/upload \
  -F "csv_file=@sample_schools.csv" \
  -F "template=$(cat sample_template.txt)")

echo "$UPLOAD_RESPONSE" | python3 -m json.tool

if echo "$UPLOAD_RESPONSE" | grep -q "success"; then
  echo "✓ Upload successful"
else
  echo "✗ Upload failed"
  exit 1
fi

# Step 2: Generate emails
echo -e "\nStep 2: Generating emails..."
GENERATE_RESPONSE=$(curl -s -b cookies.txt -X POST http://localhost:5001/generate)

echo "$GENERATE_RESPONSE" | python3 -m json.tool

if echo "$GENERATE_RESPONSE" | grep -q "total_emails"; then
  echo "✓ Generation successful"
  TOTAL=$(echo "$GENERATE_RESPONSE" | grep -o '"total_emails":[0-9]*' | grep -o '[0-9]*')
  echo "  Total emails generated: $TOTAL"
else
  echo "✗ Generation failed"
  exit 1
fi

# Step 3: Check review page
echo -e "\nStep 3: Checking review page..."
REVIEW_RESPONSE=$(curl -s -b cookies.txt http://localhost:5001/review)

if echo "$REVIEW_RESPONSE" | grep -q "email-card"; then
  EMAIL_COUNT=$(echo "$REVIEW_RESPONSE" | grep -o 'email-card' | wc -l)
  echo "✓ Review page shows $EMAIL_COUNT email cards"
else
  echo "✗ Review page failed"
  exit 1
fi

# Step 4: Test download
echo -e "\nStep 4: Testing download..."
curl -s -b cookies.txt http://localhost:5001/download -o test_output.csv

if [ -f test_output.csv ] && [ -s test_output.csv ]; then
  ROWS=$(wc -l < test_output.csv)
  echo "✓ Download successful - $ROWS rows in CSV"
  echo "  First few lines:"
  head -3 test_output.csv
  rm test_output.csv
else
  echo "✗ Download failed"
  exit 1
fi

# Cleanup
rm -f cookies.txt

echo -e "\n✅ All tests passed!"
