#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Kullanım: ./run-tests.sh <proje-adı>"
    echo "Örnek: ./run-tests.sh hello-world"
    exit 1
fi

# Prefix kontrolü: zaten product- ile başlıyorsa ekleme
if [[ "$1" == product-* ]]; then
    PROJECT_NAME="$1"
else
    PROJECT_NAME="product-$1"
fi
PROJECT_DIR="$HOME/projects/$PROJECT_NAME"
TIMESTAMP=$(date -Iseconds)
DATE=$(date +%Y-%m-%d)

if [ ! -d "$PROJECT_DIR" ]; then
    echo "HATA: $PROJECT_DIR bulunamadı!"
    exit 1
fi

cd "$PROJECT_DIR"

echo "=== AI Factory: Test Çalıştırılıyor ==="
echo "Proje: $PROJECT_NAME"
echo ""

TEST_SPECS="tests/test_specs.md"
if [ ! -f "$TEST_SPECS" ]; then
    echo "HATA: $TEST_SPECS bulunamadı!"
    exit 1
fi

TEST_TYPE=$(grep "^test_type:" "$TEST_SPECS" | cut -d: -f2 | tr -d ' ')
TEST_COMMAND=$(grep "^test_command:" "$TEST_SPECS" | cut -d: -f2- | sed 's/^ *//')

echo "Test tipi: $TEST_TYPE"
echo "Test komutu: $TEST_COMMAND"
echo ""

if [ "$TEST_TYPE" = "manual" ]; then
    echo "Manuel test - otomatik çalıştırma yok."
    echo "test_specs.md dosyasındaki checklist'i manuel kontrol edin."
    exit 0
fi

if [ -z "$TEST_COMMAND" ]; then
    echo "HATA: test_command tanımlı değil!"
    exit 1
fi

echo "[1/3] Test çalıştırılıyor..."
echo "----------------------------------------"

TEST_OUTPUT=$(mktemp)
TEST_EXIT_CODE=0

$TEST_COMMAND > "$TEST_OUTPUT" 2>&1 || TEST_EXIT_CODE=$?

cat "$TEST_OUTPUT"
echo "----------------------------------------"

echo "[2/3] Sonuçlar kaydediliyor..."

if [ $TEST_EXIT_CODE -eq 0 ]; then
    TEST_RESULT="PASSED"
    PASS_RATE="1.0"
else
    TEST_RESULT="FAILED"
    PASS_RATE="0.0"
fi

cat > reports/test_results.md << REPORT
# Test Sonuçları

**Tarih:** $DATE  
**Sonuç:** $TEST_RESULT  
**Çıkış Kodu:** $TEST_EXIT_CODE

## Komut
\`\`\`
$TEST_COMMAND
\`\`\`

## Çıktı
\`\`\`
$(cat "$TEST_OUTPUT")
\`\`\`
REPORT

rm "$TEST_OUTPUT"

echo "[3/3] State güncelleniyor..."

sed -i "s/^  test_pass_rate:.*/  test_pass_rate: $PASS_RATE/" state/state.yaml

echo ""
echo "=== Tamamlandı ==="
echo "Sonuç: $TEST_RESULT"
echo "Rapor: reports/test_results.md"
