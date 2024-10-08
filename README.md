## VoiceBridge: Приложение для асинхронного перевода и озвучки речи

**VoiceBridge** — это приложение с графическим интерфейсом, которое обеспечивает перевод и озвучку речи в режиме реального времени. 

### Возможности:

- **Распознавание речи:** Приложение прослушивает микрофон и преобразует речь в текст.
- **Перевод текста:** Переводит распознанный текст на выбранный язык.
- **Озвучка перевода:** Воспроизводит переведенный текст с помощью синтеза речи.
- **Асинхронная работа:** Приложение работает асинхронно, чтобы интерфейс оставался отзывчивым во время обработки речи и перевода.

### Технологии:

- **Python:** Язык программирования для разработки приложения.
- **CustomTkinter:**  Библиотека для создания графического интерфейса.
- **SpeechRecognition:**  Библиотека для распознавания речи.
- **Deep Translator:** Библиотека для перевода текста.
- **pyttsx3:** Библиотека для синтеза речи.
- **asyncio:**  Модуль для асинхронного программирования.

### Установка:

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/sl1dee36/VoiceBridge.git
   cd VoiceBridge
   ```

2. **Создайте виртуальное окружение (рекомендуется):**
   ```bash
   python -m venv .venv
   ```

3. **Активируйте виртуальное окружение:**
   ```bash
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```

4. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

### Запуск:

```bash
python VoiceBridge-ui.py
```

### Использование:

1. Выберите исходный и целевой языки в выпадающих меню.
2. Нажмите кнопку "Старт", чтобы начать распознавание, перевод и озвучку речи.
3. Нажмите кнопку "Стоп", чтобы остановить процесс.

### Планируемые улучшения:

- **Повышение скорости и качества перевода:** Исследование и интеграция более продвинутых моделей перевода, таких как OpenAI API или модели машинного перевода на основе нейронных сетей.
- **Улучшение распознавания речи:**  Добавление поддержки различных моделей распознавания речи, настройка чувствительности микрофона и фильтрации шума для более точного распознавания в различных условиях.
- **Расширение функциональности:**
    - Возможность сохранения переведенного текста в файл.
    - Поддержка большего количества языков.
    - Настройка голоса и скорости озвучки.
    - Интеграция с другими приложениями, например, мессенджерами.

### Вклад:

Буду рад любым предложениям и помощи в развитии проекта!  
