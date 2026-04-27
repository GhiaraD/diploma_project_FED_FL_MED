#!/bin/bash

# Manual Security Policy Testing
# Usage: ./test_policy_manual.sh [log|warn|reject]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Get policy from argument or default to "log"
POLICY=${1:-log}
MIN_VALID=${2:-0.8}

echo "========================================================================"
echo "🔐 TESTING SECURITY POLICY: $POLICY"
echo "========================================================================"
echo "Min Valid Signatures: $MIN_VALID"
echo ""

# Validate policy
if [[ ! "$POLICY" =~ ^(log|warn|reject)$ ]]; then
    echo "❌ Invalid policy: $POLICY"
    echo "Usage: $0 [log|warn|reject] [min_valid_signatures]"
    echo ""
    echo "Examples:"
    echo "  $0 log 0.8      # Test LOG policy with 80% threshold"
    echo "  $0 warn 0.8     # Test WARN policy with 80% threshold"
    echo "  $0 reject 1.0   # Test REJECT policy with 100% threshold"
    exit 1
fi

# Backup original docker-compose.yml
if [ ! -f docker-compose.yml.original ]; then
    cp docker-compose.yml docker-compose.yml.original
    echo "✓ Backed up original docker-compose.yml"
fi

# Update policy in docker-compose.yml
echo "📝 Updating docker-compose.yml with policy: $POLICY"
cp docker-compose.yml.original docker-compose.yml
sed -i "s/SIGNATURE_POLICY: \".*\"/SIGNATURE_POLICY: \"$POLICY\"/" docker-compose.yml
sed -i "s/MIN_VALID_SIGNATURES: \".*\"/MIN_VALID_SIGNATURES: \"$MIN_VALID\"/" docker-compose.yml

echo "✓ Configuration updated"
echo ""

# Verify the change
echo "📋 Current configuration:"
grep -A 1 "SIGNATURE_POLICY:" docker-compose.yml | head -2
echo ""

echo "========================================================================"
echo "🚀 READY TO TEST"
echo "========================================================================"
echo ""
echo "Policy configured: $POLICY"
echo "Min valid signatures: $MIN_VALID"
echo ""
echo "Next steps:"
echo "  1. Run: docker-compose down -v"
echo "  2. Run: docker-compose up -d"
echo "  3. Run: ./scripts/test_single_fl.sh"
echo "  4. Check logs: docker-compose logs -f central"
echo ""
echo "To restore original config:"
echo "  mv docker-compose.yml.original docker-compose.yml"
echo ""
