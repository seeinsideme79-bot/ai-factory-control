#!/bin/bash
# AI Factory - Delete Project Script
# Kullanım: ./scripts/delete-project.sh <project-name>
#
# Bu script:
# 1. Onay ister
# 2. Lokal klasörü siler
# 3. Registry'den çıkarır
# 4. Dashboard'u günceller
# 5. GitHub repo'yu archive eder

set -e

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROL_PLANE_DIR="$(dirname "$SCRIPT_DIR")"
PROJECTS_DIR="$(dirname "$CONTROL_PLANE_DIR")"
REGISTRY_FILE="$CONTROL_PLANE_DIR/registry/projects.yaml"
DASHBOARD_FILE="$CONTROL_PLANE_DIR/dashboard/dashboard.md"

# GitHub kullanıcı adı
GITHUB_USER="seeinsideme79-bot"

# Fonksiyonlar
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parametre kontrolü
if [ -z "$1" ]; then
    log_error "Kullanım: $0 <project-name>"
    echo "Örnek: $0 product-hello-world"
    exit 1
fi

PROJECT_NAME="$1"
PROJECT_PATH="$PROJECTS_DIR/$PROJECT_NAME"

# Proje var mı kontrol et
if [ ! -d "$PROJECT_PATH" ]; then
    log_error "Proje bulunamadı: $PROJECT_PATH"
    exit 1
fi

# Bilgi göster
echo ""
echo "=========================================="
echo "  PROJE SİLME - $PROJECT_NAME"
echo "=========================================="
echo ""
echo "Bu işlem şunları yapacak:"
echo "  1. Lokal klasörü silecek: $PROJECT_PATH"
echo "  2. Registry'den çıkaracak"
echo "  3. Dashboard'u güncelleyecek"
echo "  4. GitHub repo'yu archive edecek"
echo ""
echo -e "${YELLOW}DİKKAT: Bu işlem geri alınamaz!${NC}"
echo ""

# Onay iste
read -p "Devam etmek istiyor musunuz? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    log_info "İşlem iptal edildi."
    exit 0
fi

echo ""

# 1. Lokal klasörü sil
log_info "Lokal klasör siliniyor: $PROJECT_PATH"
rm -rf "$PROJECT_PATH"
log_info "Lokal klasör silindi ✓"

# 2. Registry'den çıkar
if [ -f "$REGISTRY_FILE" ]; then
    log_info "Registry güncelleniyor..."
    
    # Projeyi registry'den çıkar (basit sed ile)
    # project_id satırından bir sonraki boş satıra kadar sil
    if grep -q "project_id: $PROJECT_NAME" "$REGISTRY_FILE"; then
        # Geçici dosya oluştur
        temp_file=$(mktemp)
        
        # Python ile daha güvenli YAML işleme
        python3 << EOF
import yaml

with open('$REGISTRY_FILE', 'r') as f:
    data = yaml.safe_load(f) or {}

projects = data.get('projects', [])
data['projects'] = [p for p in projects if p.get('project_id') != '$PROJECT_NAME']

with open('$REGISTRY_FILE', 'w') as f:
    yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

print('Registry güncellendi')
EOF
        log_info "Registry güncellendi ✓"
    else
        log_warn "Proje registry'de bulunamadı, atlanıyor."
    fi
else
    log_warn "Registry dosyası bulunamadı: $REGISTRY_FILE"
fi

# 3. Dashboard güncelle
if [ -f "$CONTROL_PLANE_DIR/scripts/update-dashboard.sh" ]; then
    log_info "Dashboard güncelleniyor..."
    bash "$CONTROL_PLANE_DIR/scripts/update-dashboard.sh"
    log_info "Dashboard güncellendi ✓"
else
    log_warn "Dashboard script bulunamadı, manuel güncelleme gerekebilir."
fi

# 4. GitHub repo'yu archive et
log_info "GitHub repo archive ediliyor..."

REPO_FULL_NAME="$GITHUB_USER/$PROJECT_NAME"
TODAY=$(date +%Y-%m-%d)

# Description güncelle
if gh repo edit "$REPO_FULL_NAME" --description "[ARCHIVED] Local deleted on $TODAY" 2>/dev/null; then
    log_info "GitHub description güncellendi ✓"
else
    log_warn "GitHub description güncellenemedi (repo bulunamadı veya yetki yok)"
fi

# Archive et
if gh repo archive "$REPO_FULL_NAME" --yes 2>/dev/null; then
    log_info "GitHub repo archive edildi ✓"
else
    log_warn "GitHub repo archive edilemedi (zaten archive veya bulunamadı)"
fi

# 5. Git commit (control plane değişiklikleri)
log_info "Control plane değişiklikleri commit ediliyor..."
cd "$CONTROL_PLANE_DIR"
git add -A
git commit -m "Delete project: $PROJECT_NAME" 2>/dev/null || log_warn "Commit edilecek değişiklik yok"
git push 2>/dev/null || log_warn "Push yapılamadı"

echo ""
echo "=========================================="
echo -e "${GREEN}  PROJE SİLİNDİ: $PROJECT_NAME${NC}"
echo "=========================================="
echo ""
echo "Özet:"
echo "  - Lokal klasör: SİLİNDİ"
echo "  - Registry: GÜNCELLENDI"
echo "  - Dashboard: GÜNCELLENDI"
echo "  - GitHub: ARCHIVED"
echo ""
echo "GitHub'da repo hala mevcut (archived):"
echo "  https://github.com/$REPO_FULL_NAME"
echo ""
