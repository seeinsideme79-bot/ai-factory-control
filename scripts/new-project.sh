#!/bin/bash
set -e

CONTROL_PLANE_DIR="$HOME/projects/ai-factory-control"
PROJECTS_DIR="$HOME/projects"

if [ -z "$1" ]; then
    echo "Kullanım: ./new-project.sh <proje-adı>"
    echo "Örnek: ./new-project.sh hello-world"
    exit 1
fi

PROJECT_NAME="product-$1"
PROJECT_DIR="$PROJECTS_DIR/$PROJECT_NAME"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date -Iseconds)

echo "=== AI Factory: Yeni Proje Oluşturuluyor ==="
echo "Proje: $PROJECT_NAME"
echo "Tarih: $DATE"
echo ""

if [ -d "$PROJECT_DIR" ]; then
    echo "HATA: $PROJECT_DIR zaten mevcut!"
    exit 1
fi

echo "[1/6] GitHub repo oluşturuluyor..."
cd "$PROJECTS_DIR"
gh repo create "seeinsideme79-bot/$PROJECT_NAME" --private --clone --description "AI Factory Project: $PROJECT_NAME"
cd "$PROJECT_DIR"

echo "[2/6] Dizin yapısı oluşturuluyor..."
mkdir -p config prp state agents/overrides tests docs reports src

echo "[3/6] Template dosyaları kopyalanıyor..."
sed -e "s/__PROJECT_ID__/$PROJECT_NAME/g" \
    -e "s/__DATE__/$DATE/g" \
    -e "s/__TIMESTAMP__/$TIMESTAMP/g" \
    "$CONTROL_PLANE_DIR/templates/state.template.yaml" > state/state.yaml

cp "$CONTROL_PLANE_DIR/templates/llm.template.yaml" config/llm.yaml

echo "[4/6] Başlangıç dosyaları oluşturuluyor..."
cat > prp/prp.md << 'EOF'
# PRP - Product Requirements and Planning

## Vizyon
[Kullanıcı tarafından doldurulacak]

## Kapsam
[PRP Agent tarafından oluşturulacak]

## Gereksinimler
[PRP Agent tarafından oluşturulacak]

---
Versiyon: 0.0
Tarih: Henüz oluşturulmadı
EOF

cat > prp/prp_history.md << 'EOF'
# PRP Geçmişi

| Versiyon | Tarih | Değişiklik |
|----------|-------|------------|
| 0.0 | - | Başlangıç |
EOF

cat > tests/test_specs.md << 'EOF'
# Test Spesifikasyonları

[Test Agent tarafından oluşturulacak]
EOF

cat > docs/architecture.md << 'EOF'
# Mimari Doküman

[Doc Agent tarafından oluşturulacak]
EOF

cat > reports/test_results.md << 'EOF'
# Test Sonuçları

Henüz test çalıştırılmadı.
EOF

touch src/.gitkeep
touch agents/overrides/.gitkeep

cat > .gitignore << 'EOF'
.DS_Store
*.log
*.tmp
__pycache__/
.env
EOF

echo "[5/6] Registry güncelleniyor..."
cat >> "$CONTROL_PLANE_DIR/registry/projects.yaml" << EOF

- id: $PROJECT_NAME
  repo: https://github.com/seeinsideme79-bot/$PROJECT_NAME
  phase: idea
  created_at: $DATE
EOF

echo "[6/6] Commit ve push..."
git add .
git commit -m "Initial project structure"
git push -u origin main

cd "$CONTROL_PLANE_DIR"
git add registry/projects.yaml
git commit -m "Add $PROJECT_NAME to registry"
git push

echo ""
echo "=== Tamamlandı! ==="
echo "Proje dizini: $PROJECT_DIR"
echo "GitHub: https://github.com/seeinsideme79-bot/$PROJECT_NAME"
echo ""
echo "Sonraki adım: prp/prp.md dosyasına vizyonunuzu yazın"
