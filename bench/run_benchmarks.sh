#!/bin/bash
# Multipart Parser Benchmark Script
# Usage: ./run_benchmarks.sh [output_file]

OUTPUT_FILE="${1:-benchmark_results.txt}"
BOMBARDIER="/home/farhan/go/bin/bombardier"
SERVER="http://127.0.0.1:8000"
DURATION="10s"
CONNECTIONS="50"

# Create payloads
create_payloads() {
    # Small payload (~300B)
    python3 << 'EOF'
boundary = b'---b'
crlf = b'\r\n'
payload = b''
payload += b'-----b' + crlf
payload += b'Content-Disposition: form-data; name="field1"' + crlf + crlf
payload += b'value1' + crlf
payload += b'-----b' + crlf
payload += b'Content-Disposition: form-data; name="file"; filename="test.bin"' + crlf
payload += b'Content-Type: application/octet-stream' + crlf + crlf
payload += b'y' * 100 + crlf
payload += b'-----b--' + crlf
with open('/tmp/payload_small.txt', 'wb') as f:
    f.write(payload)
EOF

    # Large payload (1MB)
    python3 << 'EOF'
data = b'x' * (1024 * 1024)
boundary = b'---b'
crlf = b'\r\n'
payload = b''
payload += b'-----b' + crlf
payload += b'Content-Disposition: form-data; name="field1"' + crlf + crlf
payload += b'value1' + crlf
payload += b'-----b' + crlf
payload += b'Content-Disposition: form-data; name="file"; filename="large.bin"' + crlf
payload += b'Content-Type: application/octet-stream' + crlf + crlf
payload += data + crlf
payload += b'-----b--' + crlf
with open('/tmp/payload_large.txt', 'wb') as f:
    f.write(payload)
EOF
}

# Check if server is running
check_server() {
    if ! curl -s "$SERVER/health" > /dev/null 2>&1; then
        echo "ERROR: Server not running at $SERVER" >&2
        echo "Start with: cd bench && uv run gunicorn benchproject.wsgi:application -w 4 -b 127.0.0.1:8000" >&2
        exit 1
    fi
}

# Run single benchmark and extract metrics
run_benchmark() {
    local endpoint=$1
    local payload=$2

    # Run bombardier and capture output
    local output=$($BOMBARDIER -c $CONNECTIONS -d $DURATION -m POST \
        -H "Content-Type: multipart/form-data; boundary=---b" \
        -f "$payload" -l -p r "$SERVER/$endpoint" 2>&1)

    # Extract metrics
    local rps=$(echo "$output" | grep "Reqs/sec" | awk '{print $2}')
    local p50=$(echo "$output" | grep "50%" | awk '{print $2}')
    local p90=$(echo "$output" | grep "90%" | awk '{print $2}')
    local p99=$(echo "$output" | grep "99%" | awk '{print $2}')
    local reqs=$(echo "$output" | grep "2xx" | grep -oP '2xx - \K[0-9]+')

    echo "$rps|$p50|$p90|$p99|$reqs"
}

# Calculate percentage difference
calc_diff() {
    local base=$1
    local current=$2
    python3 -c "print(f'{(($current - $base) / $base * 100):+.1f}%')"
}

# Print table row
print_row() {
    printf "| %-25s | %10s | %10s | %10s | %10s | %10s |\n" "$1" "$2" "$3" "$4" "$5" "$6"
}

# Print separator
print_sep() {
    printf "+---------------------------+------------+------------+------------+------------+------------+\n"
}

# Main
echo "Creating payloads..." >&2
create_payloads

echo "Checking server..." >&2
check_server

echo "Running benchmarks (this takes ~2 minutes)..." >&2

# Run all benchmarks
echo "  Small payload - Django..." >&2
SMALL_DEFAULT=$(run_benchmark "django" "/tmp/payload_small.txt")
echo "  Small payload - python-multipart..." >&2
SMALL_FAST=$(run_benchmark "python-multipart" "/tmp/payload_small.txt")
echo "  Small payload - multipart..." >&2
SMALL_MULTI=$(run_benchmark "multipart" "/tmp/payload_small.txt")

echo "  Large payload - Django..." >&2
LARGE_DEFAULT=$(run_benchmark "django" "/tmp/payload_large.txt")
echo "  Large payload - python-multipart..." >&2
LARGE_FAST=$(run_benchmark "python-multipart" "/tmp/payload_large.txt")
echo "  Large payload - multipart..." >&2
LARGE_MULTI=$(run_benchmark "multipart" "/tmp/payload_large.txt")

# Parse results
IFS='|' read -r SD_RPS SD_P50 SD_P90 SD_P99 SD_REQS <<< "$SMALL_DEFAULT"
IFS='|' read -r SF_RPS SF_P50 SF_P90 SF_P99 SF_REQS <<< "$SMALL_FAST"
IFS='|' read -r SM_RPS SM_P50 SM_P90 SM_P99 SM_REQS <<< "$SMALL_MULTI"

IFS='|' read -r LD_RPS LD_P50 LD_P90 LD_P99 LD_REQS <<< "$LARGE_DEFAULT"
IFS='|' read -r LF_RPS LF_P50 LF_P90 LF_P99 LF_REQS <<< "$LARGE_FAST"
IFS='|' read -r LM_RPS LM_P50 LM_P90 LM_P99 LM_REQS <<< "$LARGE_MULTI"

# Calculate differences
SF_DIFF=$(calc_diff "$SD_RPS" "$SF_RPS")
SM_DIFF=$(calc_diff "$SD_RPS" "$SM_RPS")
LF_DIFF=$(calc_diff "$LD_RPS" "$LF_RPS")
LM_DIFF=$(calc_diff "$LD_RPS" "$LM_RPS")

# Output results
{
    echo "=============================================================="
    echo "         MULTIPART PARSER BENCHMARK RESULTS"
    echo "=============================================================="
    echo ""
    echo "Date: $(date)"
    echo "Server: $SERVER"
    echo "Duration: $DURATION | Connections: $CONNECTIONS"
    echo ""
    echo "--------------------------------------------------------------"
    echo "SMALL PAYLOAD (~300 bytes)"
    echo "--------------------------------------------------------------"
    print_sep
    print_row "Parser" "RPS" "p50" "p90" "p99" "vs Default"
    print_sep
    print_row "Django (default)" "$SD_RPS" "$SD_P50" "$SD_P90" "$SD_P99" "baseline"
    print_row "python-multipart" "$SF_RPS" "$SF_P50" "$SF_P90" "$SF_P99" "$SF_DIFF"
    print_row "multipart (Hellkamp)" "$SM_RPS" "$SM_P50" "$SM_P90" "$SM_P99" "$SM_DIFF"
    print_sep
    echo ""
    echo "--------------------------------------------------------------"
    echo "LARGE PAYLOAD (1 MB)"
    echo "--------------------------------------------------------------"
    print_sep
    print_row "Parser" "RPS" "p50" "p90" "p99" "vs Default"
    print_sep
    print_row "Django (default)" "$LD_RPS" "$LD_P50" "$LD_P90" "$LD_P99" "baseline"
    print_row "python-multipart" "$LF_RPS" "$LF_P50" "$LF_P90" "$LF_P99" "$LF_DIFF"
    print_row "multipart (Hellkamp)" "$LM_RPS" "$LM_P50" "$LM_P90" "$LM_P99" "$LM_DIFF"
    print_sep
    echo ""
    echo "=============================================================="
    echo "SUMMARY"
    echo "=============================================================="
    echo ""
    echo "Small Payload Winner: $(python3 -c "print('python-multipart' if $SF_RPS > $SM_RPS else 'multipart (Hellkamp)')")"
    echo "Large Payload Winner: $(python3 -c "print('python-multipart' if $LF_RPS > $LM_RPS else 'multipart (Hellkamp)')")"
    echo ""
} | tee "$OUTPUT_FILE"

echo "" >&2
echo "Results saved to: $OUTPUT_FILE" >&2
