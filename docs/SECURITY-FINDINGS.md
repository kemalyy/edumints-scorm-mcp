# Güvenlik bulguları ve kapanış kanıtları

Bu belge, sunucunun güvenlik durumunu **yeniden üretilebilir kanıtla** kaydeder: her bulgu için kod konumu,
kapatan değişiklik, testin adı ve testi koşan komut. "Geçti" iddiası yalnız aşağıdaki komutların gerçek
çıktısına dayanır. Önceki sürüm (Haziran 2025, "simüle edilen" tarihli) bu standarda uymuyordu ve
kaldırıldı; özellikle "DNS rebinding korumalı" iddiası yalnız tek çözümleme cevabını sınayan bir teste
dayanıyordu (bkz. §2.3).

## 1. Denetim kaydı

| Alan | Değer |
|---|---|
| Tarih | 2026-10-30 |
| Kod | tag `v1.9.1` (temel: `v1.9.0`) |
| Çalışma ortamı | Python 3.11.4 (imaj: `python:3.11-slim`), fastmcp 3.3.1, mcp 1.27.2, httpx 0.28.1, httpcore 1.0.9, nh3 0.3.5, lxml 6.1.1, pydantic 2.13.4, uvicorn 0.48.0, starlette 1.2.1 |
| Kaynak | Bağımsız kod incelemesi (bulgu kodları A1–A2, S1–S5, P1–P4, Q1) |
| Bağımsız doğrulama | Değişiklik sonrası ayrı bir inceleme (SNI doğrulamasını canlı TLS ile, log filtresini uvicorn açılışında, MCP SDK'nın `expires_at` reddini kaynakta denetledi) |

**Komutlar ve sonuçlar (bu commit'te):**

| Komut | Sonuç |
|---|---|
| `PYTHONPATH=. pytest tests/security -q` | 125 passed |
| `PYTHONPATH=. pytest -q` (tüm set) | 1790 passed, 11 skipped |
| `PYTHONPATH=. node tests/runtime/embed-sandbox-probe.mjs` (Chromium, HTTP aynı köken) | 4/4 kontrol geçti |
| `PYTHONPATH=. node tests/runtime/scorm-probe.mjs` | tüm kontroller geçti |

CI bu dört komutu her PR'da koşar; `embed-sandbox-probe` ve `scorm-probe` bloklayıcıdır.

## 2. Bulgular

Durum: ✅ kapandı (kod + test) · 🟡 kısmi / bilinçli sınır · ⏳ açık (karar ya da yapılandırma bekliyor).

### 2.1 Kimlik ve yetki

| # | Bulgu | Durum | Kapanış kanıtı |
|---|---|---|---|
| A2 | Süresi dolmuş `sk_` anahtarı MCP (OAuth dual-auth) yolunda çalışıyordu; süre yalnız özel HTTP rotalarında kontrol ediliyordu. | ✅ | Tek kural `auth/keys.py:key_rejection`; `ApiKeyVerifier` aynı kuralı uygular ve token'a gerçek son kullanma zamanını yazar. `tests/security/test_v191_keys.py` (iki yol aynı sonuç) + `test_v191_review_fixes.py::test_real_mcp_request_with_expired_key_is_401` (gerçek `/mcp` isteği → 401). |
| A1 | Onay kaldırılan kullanıcının anahtarları ve hâlâ geçerli OAuth token'ı çalışmaya devam ediyordu; `sub` taşımayan token'lar ortak `"unknown"` principal'ına düşüyordu. | ✅ (kod) · ⏳ (canlı zincir) | `POST /admin/principals/revoke|restore` (`ADMIN_API_TOKEN`); iptalde anahtarlar devre dışı (yarışla sonradan eklenen anahtar da doğrulayıcıda reddedilir); OAuth araç çağrıları `forbidden`, HTTP rotaları (`/keys`, `/usage`, `/projects`) 401; principal'ın preview ve indirme linkleri silinir, kalıcı demoları 404 döner (silinmez — geri alınca yeniden yayında). `sub`'sız token reddi. Portal `rejectUser`/`approveUser` bu uçları çağırır. `tests/security/test_v191_revocation.py`, `test_v191_review2.py`. **Açık:** Logto access-token TTL'i ve refresh davranışı canlıda ölçülmedi — iptal sunucu tarafında anında etkilidir; Logto, rol kaldırılınca yeni `mcp` scope'lu token vermeyi keser. |

### 2.2 Capability URL'leri (`/files`, `/preview`, `/feedback`)

| # | Bulgu | Durum | Kapanış kanıtı |
|---|---|---|---|
| S2 | Süresi dolmuş preview token'ı ile `/feedback` yazılabiliyordu (yorumlar `list_feedback` ile modele gider). Gövde boyutu okunduktan sonra kırpılıyordu. | ✅ | Tek geçerlilik kuralı (404/410); gövde ≤ 16 KB okunmadan 413; token başına dakikada 20 yorum; DB'den önce istemci başına sınır. `tests/security/test_v191_capability.py`, `test_v191_quota_ratelimit.py::test_feedback_limited_per_ip_before_db_lookup`. |
| S5 | Linki alan herkes içeriğe erişir; preview linki yorum yetkisi de taşır; iptal yolu yoktu; token'lar loglarda tam görünüyordu. | ✅ · 🟡 | `Referrer-Policy: no-referrer`, `Cache-Control: private, no-store`, `nosniff`; uvicorn erişim loglarında token maskelenir; `revoke_links` aracı; `preview(allow_feedback=false)`. `tests/security/test_v191_capability.py`, `test_v191_link_controls.py`. **Sınır:** ters proxy logları bu filtrenin dışındadır; `/demo` kalıcı yayını ayrı bir yayın yetkisi istemiyor (onaylı her kullanıcı yayınlayabilir — ürün kararı). |

### 2.3 Asset çekme ve içerik politikası

| # | Bulgu | Durum | Kapanış kanıtı |
|---|---|---|---|
| S1, P1 | Denetlenen IP ile bağlanılan IP aynı değildi (httpx host adını yeniden çözüyordu → DNS rebinding / TOCTOU); DNS çözümlemesi event loop'u bloklıyordu; `total_timeout` gerçek bir üst sınır değildi. | ✅ | DNS fetch başına bir kez, asenkron; istek denetlenen IP'ye gider, TLS SNI ve sertifika doğrulaması orijinal ada göre (httpcore 1.0.9 `sni_hostname` → `server_hostname`; canlı TLS ile yanlış SNI'nin `CERTIFICATE_VERIFY_FAILED` aldığı doğrulandı). Hop başına yeni bağlantı (aynı IP'deki başka ad önceki TLS oturumunu kullanamaz), `trust_env=False`, IP'ler sırayla denenir, toplam süre yönlendirme + gövde dahil. 6to4/Teredo içine gömülü özel IPv4 engelli. **Kapsam:** IP sabitleme `safe_fetch_asset` (tüm asset çekimleri) içindir; Openverse/Wikimedia **arama** çağrıları sabit, güvenilir host'lara gider ve asenkron denetlenir ama sabitlenmez. `tests/security/test_v191_ssrf_pinning.py`, `test_v191_review_fixes.py`, `test_ssrf_regression.py`. |
| S4 | data-URI yolu MIME kontrolü yapmıyordu; boyut decode sonrasında ölçülüyordu; base64 katı değildi. | ✅ | URL ve data-URI aynı politika: MIME izin listesi, decode öncesi boyut sınırı, `validate=True`, `image/*` (svg hariç) bayt imzası, dosya uzantısı ↔ MIME (`.html` / `.svg` etiket atlatılamaz). `tests/security/test_v191_data_uri.py`, `test_v191_review_fixes.py::test_extension_must_match_mime`. |
| — | SVG temizliği (v1.8.1) | ✅ | Allowlist (yalnız SVG ad alanı; script, foreignObject, `<style>`, `href` hedefleyen animasyon, `on*`, `xml:base`, dış `url()` kaldırılır; DTD/ENTITY reddi). `tests/test_v181_svg.py`. |

### 2.4 Gömülü HTML (`embed_html`)

| # | Bulgu | Durum | Kapanış kanıtı |
|---|---|---|---|
| S3 | iframe `sandbox="allow-scripts allow-same-origin …"`. Pakette `src` göreli (LMS kökeni) olduğundan gömülü HTML üst sayfanın DOM'una ve LMS SCORM API'sine erişebiliyordu. **Gerçek tarayıcıda kanıtlandı** (Chromium, HTTP aynı köken). | ✅ | `allow-same-origin` kaldırıldı → her modda opak köken; tek kanal postMessage köprüsü (`ev.source` kimliği). `tests/runtime/embed-sandbox-probe.mjs`: üst DOM ✗, `window.parent.API` ✗, üst pencere gezinmesi ✗, köprü ✓ — CI'da bloklayıcı. **Sınır:** paketteki `assets/*.html` LMS kökeninde doğrudan URL ile açılabilir (yazar içeriği; güven sınırı CONTRACTS §embed). Hedef LMS'lerde (SCORM Cloud, Moodle) ayrıca elle doğrulama: ⏳. |

### 2.5 Dayanıklılık

| # | Bulgu | Durum | Kapanış kanıtı |
|---|---|---|---|
| P2 | Build tekilleştirmesi atomik değildi; bekleyen iş sayısı ve bellek sınırsızdı; restart sonrası işler sonsuza dek `running` kalıyordu. | ✅ (tek-node) | Kilitli tekilleştirme; `BUILD_QUEUE_MAX` / `BUILD_PER_PRINCIPAL` → `queue_full`; açılışta yarım işler `error`; asset baytları iş başlarken yüklenir. `tests/test_build_queue.py`. |
| P3, P4 | Kota kontrolü atomik değildi; rate limiter süreç içi ve hiç temizlenmiyordu. | ✅ (tek-node) · 🟡 | Principal kilidi + araç çağrısı süresince rezervasyon (FastMCP middleware); kova temizliği. `tests/security/test_v191_quota_ratelimit.py`. **Sınır:** tek süreç/tek replica varsayımı (`docs/KNOWN-LIMITATIONS.md` §7). |

### 2.6 Önceki denetimden devralınanlar (yeniden doğrulandı)

- **HTML sanitizasyonu** (`nh3`, `*_html` alanları): `tests/security/test_xss_sanitization.py` — geçti. Bu
  test **keyfi HTML gömmenin** (embed_html) güvenliğini kanıtlamaz; o §2.4'tedir.
- **Sır taraması:** `tests/security/test_secret_scan.py` — geçti.

## 3. Kapsam dışı ve bilinen sınırlar

- Ters proxy katmanı: gövde ve hız sınırları, log maskeleme, WAF kuralları (Anthropic
  `160.79.104.0/21` ve OpenAI çıkışlarına izin) — repo dışında, yapılandırma ile doğrulanmalı.
- Çoklu replica: rate limit, kota rezervasyonu ve build kuyruğu süreç içidir.
- Logto: CIMD (Client ID Metadata Document) ve DCR ilan edilmiyor; istemciler önceden kayıtlı OAuth
  client'larıyla bağlanır (Claude, ChatGPT, Codex — `README.md`).
- Paket içindeki HTML asset'lerinin LMS kökeninde doğrudan açılması (yazar içeriği).

## 4. Sürüm ↔ dağıtım eşlemesi

Her yayında bu tablo güncellenir: canlı deployment'ın commit'i, private ve public tag'ler.

| Sürüm | Private | Public | Canlı (scorm.edumints.com) |
|---|---|---|---|
| 1.9.0 | `face884` (tag v1.9.0) | `a4be2e0` (tag v1.9.0) | 2026-10-14 elle redeploy, `get_guide` doğrulandı |
| 1.9.1 | bu dal (push öncesi) | — | — |
