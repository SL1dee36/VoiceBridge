import speech_recognition as sr
import asyncio
import logging

logger = logging.getLogger(__name__)


class MicrophoneHandler:
    def __init__(self, text_queue):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.text_queue = text_queue
        self.listening = False

    async def listen(self):
        self.listening = True
        logger.info("Микрофон активирован.")
        with self.microphone as source:
            while self.listening:
                try:
                    audio = self.recognizer.listen(source)
                    logger.debug("Аудио получено. Отправка на распознавание...")
                    text = self.recognizer.recognize_google(audio, language="ru-RU")
                    logger.debug(f"Распознанный текст: {text}")
                    await self.text_queue.put(text)
                except sr.UnknownValueError:
                    logger.warning("Не удалось распознать речь.")
                except sr.RequestError as e:
                    logger.error(f"Ошибка запроса к Google Speech Recognition: {e}")
                await asyncio.sleep(0)

    async def start(self):
        self.listening_task = asyncio.create_task(self.listen())

    async def stop(self):
        self.listening = False
        if self.listening_task:
            await self.listening_task

    def is_listening(self):
        return self.listening
