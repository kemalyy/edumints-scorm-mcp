# edumints SCORM MCP

[![License: MIT](https://img.shields.io/github/license/kemalyy/edumints-scorm-mcp)](LICENSE)
[![Release](https://img.shields.io/github/v/release/kemalyy/edumints-scorm-mcp)](https://github.com/kemalyy/edumints-scorm-mcp/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-6E56CF)](https://modelcontextprotocol.io)

## Живые демо

Три полных курса — три уровня, три визуальных стиля — созданы полностью с помощью этого
сервера и опубликованы в живом развёртывании. **Нажмите на любой скриншот, чтобы запустить.**

| [Be a Password Hero!](https://scorm.edumints.com/demo/password-hero) | [Spot the Phish](https://scorm.edumints.com/demo/spot-the-phish) | [The Ad Hominem Argument](https://scorm.edumints.com/demo/ad-hominem) |
|:---:|:---:|:---:|
| [![Демо Password Hero](docs/assets/demo-password-hero.png)](https://scorm.edumints.com/demo/password-hero) | [![Демо Spot the Phish](docs/assets/demo-spot-the-phish.png)](https://scorm.edumints.com/demo/spot-the-phish) | [![Демо Ad Hominem](docs/assets/demo-ad-hominem.png)](https://scorm.edumints.com/demo/ad-hominem) |
| 9–13 лет · безопасность в интернете · `style-playful` + собственный бренд | Онбординг для компаний · безопасность почты · `style-minimal` + корпоративный бренд | Магистратура · теория аргументации · `style-premium` |

Каждое демо: сюжетная линия, реалистичные SVG-макеты артефактов, симуляции поиска флагов,
сравнения до/после, временные шкалы, игра по кейсам и адаптивная обратная связь — с отчётностью
SCORM на уровне вопросов под капотом.

> **MCP-сервер, который собирает интерактивные SCORM-совместимые курсы электронного обучения.**
> Вы (или ИИ-клиент, например Claude) — **автор**; этот сервер — **сборщик**.
> Опишите курс как структурированную спецификацию — сервер проверит, отрисует и упакует
> **автономный SCORM-zip**, работающий в любой LMS (Moodle, SCORM Cloud, …).

**🌐 Языки:** [English](README.md) · [Türkçe](README.tr.md) · [Español](README.es.md) · [Русский](README.ru.md) · [简体中文](README.zh-CN.md) · [Azərbaycanca](README.az.md) · [Қазақша](README.kk.md) · [Кыргызча](README.ky.md)

Открытый исходный код, разработан платформой **[edumints.com](https://edumints.com)**. Создан для
**самостоятельного размещения** — запускайте на своём компьютере или сервере — и **открыт для вклада**.

---

## Идея (другой подход)

Большинство электронных курсов создаётся вручную в тяжёлых настольных программах. Здесь **ИИ-клиент
описывает курс** (цели, экраны, тесты, ветвление, медиа) через [Model Context Protocol](https://modelcontextprotocol.io),
а сервер делает сложную часть: проверку, премиальное оформление, доступный HTML-рендеринг, мост
SCORM-runtime и упаковку. Результат — пакет, соответствующий стандартам SCORM, без привязки к вендору.

**Автор = MCP-клиент · Сборщик = этот сервер.**

![Экран викторины, отрисованный встроенным плеером слайдов](docs/assets/screenshot-player.png)

## Возможности

- **28 типов экранов** — заголовок, контент, выбор ответа, верно/неверно, заполнение пропусков,
  перетаскивание, hotspot, ветвящийся сценарий, аккордеон, вкладки, карточки, сопоставление,
  сортировка, временная шкала, lottie, **управляемая симуляция ПО**, видео, итоги,
  **сценарий принятия решений**, **терминологическая гонка**, **квест-комната**,
  **интерактивная диаграмма**, **график данных**, **сравнение изображений**,
  **детализация результатов**, **опрос / рефлексия**, **компонуемая игра**, **адаптивная практика**.
- **Компонуемый игровой движок** — экран **`game`** компонует механические примитивы
  (очки/жизни/таймер/подсказки) + декларативные правила `when событие if условие then действие` +
  ветвящиеся узлы; экран **`adaptive_practice`** оценивает компетенцию (Elo или Bayesian Knowledge
  Tracing) и калибрует сложность под учащегося. Опциональная телеметрия **xAPI/cmi5**, **анти-slop
  контроль качества** (`lint_course`) и доступность игры (WCAG 2.2.1). Всё детерминированно — без LLM
  на сервере. См. `docs/GAME-ECD.md`, `docs/GAME-ADAPTIVE.md`.
- **Слайд-плеер на фиксированной сцене** — сцена 16:9, масштабируемая под любой экран, панель
  воспроизведения (play/перемотка/субтитры/меню/повтор) и **раскрытие по таймлайну**, синхронное с
  озвучкой. Меню-оглавление по разделам. Регулируемый размер сцены; полностью адаптивный/мобильный;
  встроенные SVG-иконки (без эмодзи).
- **Логика и геймификация** — переменные/состояние, условная видимость, ветвление, HUD очков и таймера.
- **Оценивание** — согласованные вопросы с обратной связью при правильном/неправильном ответе, запись
  баллов в SCORM.
- **Медиа** — межсерверная (cross-MCP) загрузка (аудио/изображение/видео из ваших MCP → `add_asset`),
  обработка через ffmpeg, **программное видео motion-graphics/визуализации данных** (HyperFrames) и
  встроенный **турецкий TTS** (Piper, офлайн) для быстрой озвучки.
- **Темы и доступность** — светлые/нейтральные/высококонтрастные пресеты, токены бренда, с учётом WCAG,
  поддержка `prefers-reduced-motion`.
- **SCORM 1.2 и 2004**, детерминированная упаковка, ограничители расходов, «тяжёлые» функции по
  подключению/лениво (ничего не грузится, если курс это не использует).

## Быстрый старт (самостоятельное размещение)

### Docker (рекомендуется)
```bash
git clone https://github.com/kemalyy/edumints-scorm-mcp.git
cd edumints-scorm-mcp
docker build -t edumints-scorm-mcp .
docker run -p 8000:8000 -v "$PWD/data:/data" edumints-scorm-mcp
# MCP-эндпоинт: http://localhost:8000/mcp   ·   health: http://localhost:8000/health
```
Образ включает всё для опциональных функций (ffmpeg, Node + HyperFrames для видео, Piper + турецкий
голос для TTS).

### Локально (Python)
```bash
python -m venv .venv && source .venv/bin/activate
pip install ".[tts]"          # ".[tts]" добавляет офлайн турецкий TTS (Piper); опустите, чтобы пропустить
python server.py              # обслуживает MCP по HTTP
```
Для генерации видео также установите Node 22+ и HyperFrames (`npm i -g hyperframes`) + ffmpeg.

### Конфигурация
Скопируйте `.env.example` и настройте (каталог данных, квоты, базовый URL, TTL). Все параметры — в
файле. Для локального запуска секреты не нужны.

## Подключение ИИ-клиента

Направьте любой MCP-клиент на `http://<ваш-хост>:8000/mcp`:
- **Claude** (десктоп/веб/Code) — добавьте как коннектор / MCP-сервер.
- **Antigravity** и другие MCP-клиенты — тот же эндпоинт (HTTP/Streamable).

Затем попросите: *«Создай 6-минутный интерактивный курс по теме X с тестом и итогами.»* Клиент вызовет
инструменты ниже; вы получите загружаемый SCORM-zip.

> Работает в паре со **skill для авторинга** (Claude Agent Skill, обучающим ИИ-клиента создавать
> качественные курсы с этим сервером): https://github.com/kemalyy/edumints-scorm-skill

## Ключевые инструменты (MCP)

| Инструмент | Назначение |
|---|---|
| `build_from_spec` | Одна JSON-спецификация → проверенный проект + упакованный SCORM-zip (основной путь) |
| `create_project` / `add_screen` / `update_screen` / … | Гранулярное, инкрементальное редактирование |
| `set_theme` / `set_tracking` | Темы + правила завершения/оценивания |
| `add_asset` | Загрузка аудио/изображений/видео (data-URI или https, защита от SSRF) |
| `synthesize_speech` | Встроенная турецкая озвучка (Piper, офлайн) → аудио-ресурс |
| `make_video_from_image_audio` / `render_motion_video` / `render_screen_video` | Видео (ffmpeg / HyperFrames) |
| `preview` / `validate_package` / `build_package` | Предпросмотр, проверка, загрузка SCORM-zip |

## Архитектура

```
MCP-клиент (автор)  ──►  scorm-mcp (сборщик)
                          ├─ core/        модели (Pydantic), упаковка, хранилище
                          ├─ components/  HTML-рендерер + движок runtime + компилятор видео
                          ├─ auth/        API-ключ + OAuth, защита SSRF
                          ├─ themes/      токены дизайна / пресеты
                          ├─ runtime/     встроенный SCORM-runtime (scorm-again, MIT)
                          └─ server.py    инструменты FastMCP (HTTP)
```
Результат: автономный `index.html` + `imsmanifest.xml` + ресурсы + SCORM-runtime, в zip.

## Вклад

Issues и PR приветствуются. Кодовая база предпочитает небольшие сфокусированные модули, аддитивные
изменения и обратную совместимость. См. [CONTRIBUTING.md](CONTRIBUTING.md).

## Тестирование

Запуск тестов: `pytest`.

## Лицензии

- Этот проект: **MIT** — см. [LICENSE](LICENSE).
- Встроенные сторонние компоненты (scorm-again, lottie-web): см. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Разработано **edumints.com**. SCORM — товарный знак ADL; другие упомянутые названия продуктов являются
товарными знаками их владельцев (только номинативное использование).


<!-- synced: d398775 -->
