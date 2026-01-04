#!/bin/bash
set -e

CONTROL_PLANE_DIR="$HOME/projects/ai-factory-control"
PROJECTS_DIR="$HOME/projects"
REGISTRY_FILE="$CONTROL_PLANE_DIR/registry/projects.yaml"
DATE=$(date +%Y-%m-%d)

echo "=== AI Factory: Registry Senkronize Ediliyor ==="

# Proje listesini al
PROJECT_IDS=$(grep "id: product-" "$REGISTRY_FILE" | cut -d: -f2 | tr -d ' ')

UPDATED=0

for PROJECT_ID in $PROJECT_IDS; do
    STATE_FILE="$PROJECTS_DIR/$PROJECT_ID/state/state.yaml"
    
    if [ -f "$STATE_FILE" ]; then
        ACTUAL_PHASE=$(grep "^phase:" "$STATE_FILE" | cut -d: -f2 | tr -d ' ')
        REGISTRY_PHASE=$(grep -A3 "id: $PROJECT_ID" "$REGISTRY_FILE" | grep "phase:" | cut -d: -f2 | tr -d ' ')
        
        if [ "$ACTUAL_PHASE" != "$REGISTRY_PHASE" ]; then
            echo "[$PROJECT_ID] phase: $REGISTRY_PHASE → $ACTUAL_PHASE"
            sed -i "/id: $PROJECT_ID/,/created_at:/ s/phase: .*/phase: $ACTUAL_PHASE/" "$REGISTRY_FILE"
            UPDATED=$((UPDATED + 1))
        else
            echo "[$PROJECT_ID] phase: $ACTUAL_PHASE (güncel)"
        fi
    else
        echo "[$PROJECT_ID] UYARI: State dosyası bulunamadı"
    fi
done

# last_updated güncelle
sed -i "s/^last_updated:.*/last_updated: $DATE/" "$REGISTRY_FILE"

echo ""
echo "=== Tamamlandı ==="
echo "Güncellenen: $UPDATED proje"
