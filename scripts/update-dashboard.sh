#!/bin/bash
set -e

CONTROL_PLANE_DIR="$HOME/projects/ai-factory-control"
PROJECTS_DIR="$HOME/projects"
DASHBOARD_FILE="$CONTROL_PLANE_DIR/dashboard/dashboard.md"
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)

echo "=== AI Factory: Dashboard Güncelleniyor ==="

# Proje listesini al
PROJECT_IDS=$(grep "id: product-" "$CONTROL_PLANE_DIR/registry/projects.yaml" | cut -d: -f2 | tr -d ' ')

# Dashboard başlığı
cat > "$DASHBOARD_FILE" << EOF
# AI Factory Dashboard

**Son Güncelleme:** $DATE $TIME

## Proje Durumları

| Proje | Phase | Blocked | Test Pass | Next Action | Awaiting |
|-------|-------|---------|-----------|-------------|----------|
EOF

# Her proje için satır ekle
for PROJECT_ID in $PROJECT_IDS; do
    STATE_FILE="$PROJECTS_DIR/$PROJECT_ID/state/state.yaml"
    
    if [ -f "$STATE_FILE" ]; then
        PHASE=$(grep "^phase:" "$STATE_FILE" | cut -d: -f2 | tr -d ' ')
        IS_BLOCKED=$(grep "^  is_blocked:" "$STATE_FILE" | cut -d: -f2 | tr -d ' ')
        PASS_RATE=$(grep "^  test_pass_rate:" "$STATE_FILE" | cut -d: -f2 | tr -d ' ')
        NEXT_ACTION=$(grep -A1 "^next_action:" "$STATE_FILE" | grep "action:" | cut -d: -f2- | sed 's/^ *//' | cut -c1-30)
        AWAITING_HUMAN=$(grep "^  awaiting_human:" "$STATE_FILE" | cut -d: -f2 | tr -d ' ')
        
        # Format blocked
        if [ "$IS_BLOCKED" = "true" ]; then
            BLOCKED_DISPLAY="🔴 Yes"
        else
            BLOCKED_DISPLAY="🟢 No"
        fi
        
        # Format pass rate
        if [ "$PASS_RATE" = "null" ]; then
            PASS_DISPLAY="-"
        elif [ "$PASS_RATE" = "1.0" ]; then
            PASS_DISPLAY="✅ 100%"
        elif [ "$PASS_RATE" = "0.0" ]; then
            PASS_DISPLAY="❌ 0%"
        else
            PASS_DISPLAY="$PASS_RATE"
        fi
        
        # Format awaiting
        if [ "$AWAITING_HUMAN" = "true" ]; then
            AWAITING_DISPLAY="👤 Human"
        else
            AWAITING_DISPLAY="🤖 Agent"
        fi
        
        echo "| $PROJECT_ID | $PHASE | $BLOCKED_DISPLAY | $PASS_DISPLAY | $NEXT_ACTION | $AWAITING_DISPLAY |" >> "$DASHBOARD_FILE"
    else
        echo "| $PROJECT_ID | ❓ | ❓ | - | State dosyası bulunamadı | - |" >> "$DASHBOARD_FILE"
    fi
done

# Özet bölümü
cat >> "$DASHBOARD_FILE" << EOF

## Özet

EOF

TOTAL=$(echo "$PROJECT_IDS" | wc -w)
echo "- **Toplam Proje:** $TOTAL" >> "$DASHBOARD_FILE"

# Phase sayıları
for PHASE in idea prp development test human_validation release; do
    COUNT=0
    for PROJECT_ID in $PROJECT_IDS; do
        STATE_FILE="$PROJECTS_DIR/$PROJECT_ID/state/state.yaml"
        if [ -f "$STATE_FILE" ]; then
            P=$(grep "^phase:" "$STATE_FILE" | cut -d: -f2 | tr -d ' ')
            if [ "$P" = "$PHASE" ]; then
                COUNT=$((COUNT + 1))
            fi
        fi
    done
    if [ $COUNT -gt 0 ]; then
        echo "- **$PHASE:** $COUNT" >> "$DASHBOARD_FILE"
    fi
done

echo ""
echo "=== Tamamlandı ==="
echo "Dashboard: $DASHBOARD_FILE"
