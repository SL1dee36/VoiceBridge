import asyncio
from deep_translator import GoogleTranslator
import logging

logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, text_queue, translated_queue, source_lang="ru", target_lang="en"):
        self.text_queue = text_queue
        self.translated_queue = translated_queue
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.running = False

    async def translate(self):
        self.running = True
        logger.info("Поток перевода запущен.")
        while self.running:
            if not self.text_queue.empty():
                text = await self.text_queue.get()
                logger.debug(f"Получен текст для перевода: {text}")
                # Проверка на пустой текст
                if text.strip():
                    try:
                        translation = GoogleTranslator(source=self.source_lang, target=self.target_lang).translate(
                            text)
                        if translation:
                            logger.debug(f"Перевод: {translation}")
                            await self.translated_queue.put(translation)
                        else:
                            logger.error(f"Ошибка перевода: не удалось получить перевод для текста '{text}'")
                    except Exception as e:
                        logger.error(f"Ошибка перевода: {e}")
                else:
                    logger.warning("Получен пустой текст для перевода.")
            await asyncio.sleep(0) # Добавляем cooperative multitasking
        logger.info("Поток перевода остановлен.")

    async def start(self):
        self.translation_task = asyncio.create_task(self.translate())

    async def stop(self):
        self.running = False
        if self.translation_task:
            await self.translation_task