import asyncio
import pyttsx3
import logging

logger = logging.getLogger(__name__)


class VoiceOutput:
    def __init__(self):
        self.engine = pyttsx3.init()

    async def speak(self, text):
        logger.debug(f"Озвучивание текста: {text}")
        self.engine.say(text)
        self.engine.runAndWait()
        await asyncio.sleep(0)  # Добавляем cooperative multitasking

    def stop(self):
        self.engine.stop()