#!/bin/bash
set -e

usage() {
    echo "Kullanım: ./update-state.sh <proje-adı> <alan> <değer>"
    echo ""
    echo "Alanlar:"
    echo "  phase         - idea|prp|development|test|human_validation|release"
    echo "  prp-version   - PRP versiyonu (örn: 1.0)"
    echo "  code-version  - Kod versiyonu (örn: 0.1.0)"
    echo "  docs-version  - Docs versiyonu (örn: 1.0)"
    echo "  blocked       - true|false"
    echo "  block-reason  - test_failure|awaiting_human|agent_error|null"
    echo ""
    echo "Örnek: ./update-state.sh hello-world phase development"
    exit 1
}

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
    usage
fi

PROJECT_NAME="product-$1"
PROJECT_DIR="$HOME/projects/$PROJECT_NAME"
FIELD="$2"
VALUE="$3"
TIMESTAMP=$(date -Iseconds)

if [ ! -d "$PROJECT_DIR" ]; then
    echo "HATA: $PROJECT_DIR bulunamadı!"
    exit 1
fi

cd "$PROJECT_DIR"
STATE_FILE="state/state.yaml"

echo "=== AI Factory: State Güncelleniyor ==="
echo "Proje: $PROJECT_NAME"
echo "Alan: $FIELD"
echo "Değer: $VALUE"
echo ""

case "$FIELD" in
    phase)
        sed -i "s/^phase:.*/phase: $VALUE/" "$STATE_FILE"
        ;;
    prp-version)
        sed -i "s/^  prp:.*/  prp: \"$VALUE\"/" "$STATE_FILE"
        ;;
    code-version)
        sed -i "s/^  code:.*/  code: \"$VALUE\"/" "$STATE_FILE"
        ;;
    docs-version)
        sed -i "s/^  docs:.*/  docs: \"$VALUE\"/" "$STATE_FILE"
        ;;
    blocked)
        if [ "$VALUE" = "true" ]; then
            sed -i "s/^  is_blocked:.*/  is_blocked: true/" "$STATE_FILE"
            sed -i "s/^  since:.*/  since: $TIMESTAMP/" "$STATE_FILE"
        else
            sed -i "s/^  is_blocked:.*/  is_blocked: false/" "$STATE_FILE"
            sed -i "s/^  reason:.*/  reason: null/" "$STATE_FILE"
            sed -i "s/^  since:.*/  since: null/" "$STATE_FILE"
        fi
        ;;
    block-reason)
        sed -i "s/^  reason:.*/  reason: $VALUE/" "$STATE_FILE"
        ;;
    *)
        echo "HATA: Bilinmeyen alan: $FIELD"
        usage
        ;;
esac

echo "Güncellendi: $STATE_FILE"
echo ""
grep -A2 "^$FIELD\|^phase\|^version\|^blocking" "$STATE_FILE" | head -20
