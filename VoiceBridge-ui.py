import customtkinter as ctk
import asyncio
from asyncio import Queue
from src.vb_mic import MicrophoneHandler
from src.vb_ai_translator import Translator
from src.vb_voiceupper import VoiceOutput
import logging

# Настройка логгирования
logging.basicConfig(filename='voicebridge.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

class VoiceBridgeApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("VoiceBridge")
        self.geometry("400x400")

        self.source_lang = ctk.StringVar(value="ru")
        self.target_lang = ctk.StringVar(value="en")

        self.create_widgets()

        self.text_queue = Queue()
        self.translated_queue = Queue()

        self.microphone_handler = MicrophoneHandler(self.text_queue)
        self.translator = Translator(self.text_queue, self.translated_queue,
                                      source_lang=self.source_lang.get(),
                                      target_lang=self.target_lang.get())
        self.voice_output = VoiceOutput()

        self.translating = False

    def create_widgets(self):
        # Фрейм для настроек языка
        lang_frame = ctk.CTkFrame(self, width=400)
        lang_frame.pack(pady=20,padx=20)
        lang_frame.pack_propagate(0)

        source_label = ctk.CTkLabel(lang_frame, text="Исходный язык:")
        source_label.grid(row=0, column=0, padx=5,pady=5)
        source_optionmenu = ctk.CTkOptionMenu(lang_frame, variable=self.source_lang,
                                              values=["ru", "en", "fr", "es", "de"])
        source_optionmenu.grid(row=0, column=1, padx=5)

        target_label = ctk.CTkLabel(lang_frame, text="Язык перевода:")
        target_label.grid(row=1, column=0, padx=5,pady=5)
        target_optionmenu = ctk.CTkOptionMenu(lang_frame, variable=self.target_lang,
                                              values=["en", "ru", "fr", "es", "de"])
        target_optionmenu.grid(row=1, column=1, padx=5)

        # Кнопка старт/стоп
        self.start_stop_button = ctk.CTkButton(self, text="Старт",
                                                command=lambda: asyncio.create_task(self.start_stop_translation()))
        self.start_stop_button.pack(pady=20)

        # Текстовое поле для вывода распознанного текста
        self.recognized_text = ctk.CTkTextbox(self, width=400, height=50)
        self.recognized_text.pack(pady=(0, 20),padx=20)

        # Текстовое поле для вывода перевода
        self.translation_text = ctk.CTkTextbox(self, width=400, height=100)
        self.translation_text.pack(padx=20)

    async def start_stop_translation(self):
        if not self.translating:
            self.translating = True
            self.start_stop_button.configure(text="Стоп")
            asyncio.create_task(self.microphone_handler.start())
            asyncio.create_task(self.translator.start())
            asyncio.create_task(self.update_translation())

        else:
            self.translating = False
            self.start_stop_button.configure(text="Старт")
            await self.microphone_handler.stop()
            await self.translator.stop()
            self.voice_output.stop()

    async def update_translation(self):
        logging.info("Поток обновления перевода запущен.")
        while self.translating:
            if not self.text_queue.empty():
                recognized_text = await self.text_queue.get()  # Получаем распознанный текст
                self.recognized_text.insert(ctk.END, f"{recognized_text}\n")  # Выводим распознанный текст
                self.recognized_text.see(ctk.END)

            if not self.translated_queue.empty():
                translated_text = await self.translated_queue.get()
                logging.debug(f"Получен перевод: {translated_text}")
                self.translation_text.insert(ctk.END, f"{translated_text}\n")
                asyncio.create_task(self.voice_output.speak(translated_text))
                self.translation_text.see(ctk.END)

            await asyncio.sleep(0)
        logging.info("Поток обновления перевода остановлен.")

    async def run(self):
        while True:
            self.update() 
            await asyncio.sleep(0.01)  # Небольшая задержка, чтобы не нагружать процессор
        
if __name__ == "__main__":
    app = VoiceBridgeApp()
    asyncio.run(app.run())
