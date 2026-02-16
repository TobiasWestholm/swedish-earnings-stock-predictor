#!/bin/bash
# Monitor comparison backtest and display results when complete

# Usage: ./check_comparison_results.sh [output_file]
OUTPUT_FILE="${1:-./backtest_output.txt}"

echo "Monitoring backtest comparison..."
echo "Output file: $OUTPUT_FILE"
echo "Waiting for completion..."
echo ""

# Wait for process to complete
while ps aux | grep "compare_strategies.py" | grep -v grep > /dev/null; do
    sleep 5
done

echo "✓ Backtest complete!"
echo ""
echo "="
echo "RESULTS"
echo "="
echo ""

# Show the comparison table
tail -n 100 "$OUTPUT_FILE" | grep -A 50 "STRATEGY COMPARISON"

echo ""
echo "Full output available at: $OUTPUT_FILE"
