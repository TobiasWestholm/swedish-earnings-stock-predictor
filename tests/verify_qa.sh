#!/bin/bash
# Quick verification script for earnings extraction QA

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║              EARNINGS EXTRACTION VERIFICATION                        ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Verify lookback is 28 days
echo "1. Checking lookback period..."
if grep -q "lookback_days: int = 28" src/utils/scheduler.py; then
    echo "   ✓ Lookback period: 28 days"
else
    echo "   ✗ Lookback not set to 28 days"
fi

# 2. Verify trades are never cleared
echo ""
echo "2. Checking trade persistence..."
if ! grep -r "DELETE FROM hypothetical_trades" src/; then
    echo "   ✓ No code deletes hypothetical_trades"
else
    echo "   ✗ WARNING: Code may delete trades"
fi

# 3. Verify extraction runs before cleanup
echo ""
echo "3. Checking extraction order..."
if grep -A 10 "Extract earnings intraday data" src/utils/scheduler.py | grep -q "before clearing"; then
    echo "   ✓ Extraction runs BEFORE clearing"
else
    echo "   ⚠ Check extraction order manually"
fi

# 4. Run comprehensive tests
echo ""
echo "4. Running integrity tests..."
./venv/bin/python tests/test_earnings_extraction_integrity.py | tail -10

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                    VERIFICATION COMPLETE                             ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
