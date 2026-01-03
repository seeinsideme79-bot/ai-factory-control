# AI Factory Dashboard

> Son güncelleme: [timestamp]

## Aktif Projeler

| Proje | Phase | Durum | Bekleyen | Son İşlem |
|-------|-------|-------|----------|-----------|
| - | - | - | - | - |

## Bekleyen Aksiyonlar

### Human Approval Gerekli
- [ ] Henüz yok

### Agent Tetikleme Bekliyor
- [ ] Henüz yok

## Son Olaylar

| Zaman | Proje | Agent | Aksiyon | Sonuç |
|-------|-------|-------|---------|-------|
| - | - | - | - | - |

## Blocked Projeler

| Proje | Sebep | Bekleme Süresi |
|-------|-------|----------------|
| - | - | - |

## Sistem Durumu

- Control Plane: ✅ Aktif
- Projeler: 0
- Bekleyen: 0
- Blocked: 0

---

## Kullanım

### Yeni Proje Başlat
1. `registry/projects.yaml` dosyasına proje ekle
2. GitHub'da `product-{name}` reposu oluştur
3. Project structure template'i uygula
4. İlk vizyon ile PRP agent'ı tetikle

### Agent Tetikleme
Dashboard üzerinden manuel tetikleme için:
1. İlgili projenin state.yaml dosyasını kontrol et
2. `next_action` alanına göre agent'ı belirle
3. Cline'da ilgili agent prompt'unu çalıştır

### Onay Verme
1. İlgili artifact'ı incele (PRP, test results, vb.)
2. Uygunsa state.yaml'da phase'i ilerlet
3. Değilse feedback ekle, revizyon tetikle
