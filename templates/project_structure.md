# Project Structure Template

Yeni proje reposu oluştururken bu yapıyı kullan.

## Klasör Yapısı
```
product-{name}/
├── config/
│   └── llm.yaml           # LLM ayarları
├── prp/
│   ├── prp.md             # Ana PRP dokümanı
│   └── prp_history.md     # PRP değişiklik geçmişi
├── state/
│   └── state.yaml         # Proje durumu (tek kaynak)
├── agents/
│   └── overrides/         # Agent prompt override'ları
├── tests/
│   └── test_specs.md      # Test tanımları
├── docs/
│   └── architecture.md    # Teknik dokümantasyon
├── reports/
│   └── test_results.md    # Test sonuçları
├── src/                   # Kaynak kod
├── .gitignore
└── README.md
```

## Zorunlu Dosyalar

Her projede şu dosyalar olmalı:
1. `state/state.yaml` - State schema'ya uygun
2. `config/llm.yaml` - LLM config schema'ya uygun
3. `prp/prp.md` - PRP template'e uygun
4. `README.md` - Proje özeti

## Oluşturma Komutları
```bash
# Yeni proje oluştur
mkdir -p product-{name}/{config,prp,state,agents/overrides,tests,docs,reports,src}

# Zorunlu dosyaları oluştur
touch product-{name}/config/llm.yaml
touch product-{name}/prp/prp.md
touch product-{name}/state/state.yaml
touch product-{name}/README.md
```

## Naming Convention

- Repo adı: `product-{name}` (lowercase, hyphen-separated)
- Branch: `main` (default), `feature/{name}`, `fix/{name}`
- Commit: `[agent]: action description`
