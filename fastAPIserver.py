import os
import wave
import json
import base64
import yt_dlp
import moviepy.editor as mp
from urllib.parse import urlparse
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from vosk import Model, KaldiRecognizer
from pydub import AudioSegment
from datetime import datetime


app = FastAPI()

# Папка для сохранения загруженных файлов
UPLOAD_DIRECTORY = "uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# Путь к модели Vosk
model_path = r"C:\Users\culdc\Coding\suShef\vosk-model-ru-0.42"  # Замени на путь к модели
# Загрузка модели
t0 = datetime.now()
if not os.path.exists(model_path):
    print(f"Модель {model_path} не найдена. Скачайте и укажите правильный путь.")
    exit(1)
print("start model...")
model = Model(model_path)
print("end model...", datetime.now() - t0)

def download_video(url, output_path):
    # Настройки для yt-dlp
    ydl_opts = {
        'format': 'best',  # Скачать лучшее качество
        'outtmpl': output_path,  # Имя выходного файла
    }
    print("Скачивание видео...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def extract_audio_from_video(video_file, audio_file):
    print(f"Извлечение аудио из видеофайла и сохранение в {audio_file}.")
    video = mp.VideoFileClip(video_file)
    video.audio.write_audiofile(audio_file, fps=16000, codec='pcm_s16le')
    audio = AudioSegment.from_file(audio_file)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(audio_file, format="wav")


def save_frame(video_tmp_file, sec):
    # saving a frame at 2 second
    clip = mp.VideoFileClip(video_tmp_file)
    clip.save_frame("frame2.png", t=sec)
    with open("frame2.png", "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read())
    return encoded_string


class URLRequest(BaseModel):
    url: str


@app.post("/post-url/")
async def post_url(url_request: URLRequest):
    try:
        video_url = url_request.url
        url_parse = urlparse(video_url)
        video_tmp_file = url_parse.netloc + o.path.replace('/', '_') + '.mp4'
        audio_tmp_file = url_parse.netloc + o.path.replace('/', '_') + '.wav'
        download_video(video_url, video_tmp_file)
        extract_audio_from_video(video_tmp_file, audio_tmp_file)
        print("Открываем аудиофайл...")
        wf = wave.open(audio_tmp_file, "rb")
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
            print("Аудиофайл должен быть в формате mono WAV с частотой 16000 Hz.")
            exit(1)
        print("Инициализация распознавателя")
        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)  # Включаем вывод временных меток для слов

        results = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                results.append(result)
            else:
                result = json.loads(rec.PartialResult())

        # Получаем финальный результат
        final_result = json.loads(rec.FinalResult())
        results.append(final_result)
        subtitles = []
        # frames = []
        for i in results['result']:
            if len(i['text']) > 2:
                subtitles.append({"frame": save_frame(video_tmp_file, i['result'][0]['start']),
                                  "text": i['text'],
                                  "start": i['result'][0]['start'],
                                  "end": i['result'][-1]['end']})



        # Возвращаем JSON с именем файла и сообщением об успешной загрузке
        return JSONResponse(content={
            "filename": audio_tmp_file,
            "message": "File uploaded successfully",
            "result": results,
            "subtitles": subtitles
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/upload-audio/")
# async def upload_audio(file: UploadFile = File(...)):
#     try:
#         # Сохраняем файл на сервере
#         file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
#         with open(file_location, "wb+") as file_object:
#             file_object.write(file.file.read())
#
#         print("Открываем аудиофайл...")
#         wf = wave.open(file_location, "rb")
#         if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
#             print("Аудиофайл должен быть в формате mono WAV с частотой 16000 Hz.")
#             exit(1)
#
#         print("Инициализация распознавателя")
#         rec = KaldiRecognizer(model, wf.getframerate())
#         rec.SetWords(True)  # Включаем вывод временных меток для слов
#         print("wf.getframerate()= ", wf.getframerate())
#         print("getparams= ", wf.getparams())
#         print("getnframes= ", wf.getnframes())
#         # Чтение и обработка аудио
#         results = []
#         while True:
#             data = wf.readframes(4000)
#             if len(data) == 0:
#                 break
#             if rec.AcceptWaveform(data):
#                 result = json.loads(rec.Result())
#                 results.append(result)
#             else:
#                 result = json.loads(rec.PartialResult())
#
#         # Получаем финальный результат
#         final_result = json.loads(rec.FinalResult())
#         results.append(final_result)
#
#         # Возвращаем JSON с именем файла и сообщением об успешной загрузке
#         return JSONResponse(content={
#             "filename": file.filename,
#             "message": "File uploaded successfully",
#             "file_location": file_location,
#             "result": results
#         })
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)