# Yük ve Regresyon Testleri

Bu dizin, `scorm-mcp` sunucusunun build performansını ve paket boyutlarını ölçen araçları içerir.

## Build Yük Testi

Eşzamanlı isteklerle çekirdek build kapasitesini ölçer.

```bash
# Yerel (in-memory) test
python tests/load/load_build.py -c 16 -n 300

# Uzak sunucu testi
MCP_URL=http://localhost:8000/mcp API_KEY=<key> \
  python tests/load/load_build.py -c 16 -n 300
```

## Regresyon Testi

10, 50 ve 100 ekranlı sentetik kurslar oluşturur; build süresini ve paket boyutunu ölçer. Eşikler aşılırsa başarısız olur.

```bash
python tests/load/load_build.py --regression
```

Sonuçlar `tests/load/regression_results.json` ve `tests/load/regression_results.csv` dosyalarına yazılır.

### Eşik Mantığı ve Yapılandırma

Varsayılan eşikler:
- 10 ekran: 2.0s, 600KB
- 50 ekran: 5.0s, 1200KB
- 100 ekran: 10.0s, 2500KB

Kendi eşiklerinizi bir JSON dosyası ile verebilirsiniz:

```bash
python tests/load/load_build.py --regression --thresholds my_thresholds.json
```

`my_thresholds.json` formatı:
```json
{
  "10": {"time": 1.5, "size_kb": 500},
  "50": {"time": 4.0, "size_kb": 1000},
  "100": {"time": 8.0, "size_kb": 2000}
}
```

## Smoke Test (K6)

HTTP katmanını test etmek için:
```bash
k6 run tests/load/k6_smoke.js
```
