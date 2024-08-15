import os
import yt_dlp
import PySimpleGUI as sg
import threading
from googletrans import Translator
import time

def translate_subtitles(path_to_content, target_lang='ru', window=None, max_retries=3):
    lang = path_to_content.split('.')[-2][:2]

    with open(path_to_content, 'r', encoding='utf-8') as file:
        subtitle_content = file.read()

    translator = Translator()
    translated_lines = []
    lines = subtitle_content.split('\n')

    for i, line in enumerate(lines):
        if line.strip() and not line.strip().isdigit() and '-->' not in line:
            translated_text = line
            for attempt in range(max_retries):
                try:
                    translated_text = translator.translate(line, src='auto', dest=target_lang).text
                    break
                except Exception as e:
                    print(f"Error translating line {i}: {e}")
                    time.sleep(1)
            translated_lines.append(translated_text)
        else:
            translated_lines.append(line)

        if window:
            window.write_event_value('-TRANSLATE_PROGRESS-', int((i + 1) / len(lines) * 100))

    return '\n'.join(translated_lines), lang

def save_translated_subtitles(translated_content, original_path, lang, filename_suffix='-ru_translated', ext='srt'):
    dir_name = os.path.dirname(original_path)
    translated_filename = f"{lang}{filename_suffix}.{ext}"
    translated_path = os.path.join(dir_name, translated_filename)
    with open(translated_path, 'w', encoding='utf-8') as file:
        file.write(translated_content)
    return translated_path

def download_content(url, content_type, output_folder, resolution, window):
    ydl_opts = {
        'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),  # Save directly to the selected folder
        'socket_timeout': 10,  # Timeout for socket operations
        'retries': 10,  # Number of retries
        'progress_hooks': [lambda d: progress_hook(d, window)]
    }

    if content_type == 'video':
        if resolution == 'best':
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
        else:
            ydl_opts['format'] = f'bestvideo[height<={resolution}]+bestaudio/best'
        ydl_opts['merge_output_format'] = 'mp4'
    elif content_type == 'subtitles':
        ydl_opts.update({
            'skip_download': True,
            'subtitleslangs': ['ru', 'en', 'ja', 'ko'],
            'writesubtitles': True,
            'writeautomaticsub': True,
            'postprocessors': [
                {'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'}  # Convert subtitles to SRT
            ]
        })
    elif content_type == 'thumbnail':
        ydl_opts['skip_download'] = True
        ydl_opts['writethumbnail'] = True
        ydl_opts['embedthumbnail'] = False

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        window.write_event_value(f'-{content_type.upper()}_FINISHED-', f'{content_type.capitalize()} Download Complete')
    except Exception as e:
        window.write_event_value('-ERROR-', str(e))

def progress_hook(d, window):
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate')
        downloaded = d.get('downloaded_bytes', 0)
        percent = int(downloaded / total * 100) if total else 0
        window.write_event_value('-PROGRESS-', percent)

def animate_loading(window):
    while True:
        for i in range(1, 9):
            window['LOADING_IMAGE'].update(f'loading_images/{i}.png')
            time.sleep(0.1)

def main():
    layout = [
        [sg.Text('URL видео:')],
        [sg.InputText(size=(65, 1), key='URL')],
        [sg.FolderBrowse('Выбрать папку', target='FOLDER'), sg.InputText(key='FOLDER', size=(50, 1))],
        [sg.Text('Выберите разрешение видео:')],
        [sg.Combo(['best', '1080', '720', '480', '360', '240'], default_value='best', key='RESOLUTION')],
        [sg.Submit('Скачать видео'), sg.Submit('Скачать титры'), sg.Submit('Скачать обложку')],
        [sg.Text('Состояние загрузки:')],
        [sg.ProgressBar(100, orientation='h', size=(34, 20), key='PROGRESS_BAR')],
        [sg.Image(key='LOADING_IMAGE')],
        [sg.HorizontalSeparator()],
        [sg.Text('Выберите файл титров:')],
        [sg.Input(key='FILE'), sg.FilesBrowse()],
        [sg.Submit('Перевести')],
        [sg.Text('Состояние перевода:')],
        [sg.ProgressBar(100, orientation='h', size=(34, 20), key='TRANSLATE_BAR')],
    ]

    window = sg.Window('Download YouTube Content', layout)

    while True:
        event, values = window.read()

        if event in (sg.WINDOW_CLOSED, 'Exit'):
            break

        if event in ('Скачать видео', 'Скачать титры', 'Скачать обложку'):
            url = values['URL']
            output_folder = values['FOLDER']
            if not output_folder:
                sg.popup_error('Выберите папку для сохранения!')
                continue

            resolution = values['RESOLUTION']
            content_type = 'video' if event == 'Скачать видео' else 'subtitles' if event == 'Скачать титры' else 'thumbnail'
            threading.Thread(target=download_content, args=(url, content_type, output_folder, resolution, window)).start()
            threading.Thread(target=animate_loading, args=(window,), daemon=True).start()

        if event == '-PROGRESS-':
            percent = values[event]
            window['PROGRESS_BAR'].update(percent)

        if event in ('-VIDEO_FINISHED-', '-SUBTITLES_FINISHED-', '-THUMBNAIL_FINISHED-'):
            sg.popup(values[event])
            window['PROGRESS_BAR'].update(0)
            window['LOADING_IMAGE'].update('')

        if event == '-ERROR-':
            sg.popup_error(f"An error occurred: {values[event]}")
            window['PROGRESS_BAR'].update(0)
            window['LOADING_IMAGE'].update('')

        if event == 'Перевести':
            path_to_content = values['FILE']
            if path_to_content:
                threading.Thread(target=translate_subtitles_thread, args=(path_to_content, window)).start()

        if event == '-TRANSLATE_PROGRESS-':
            percent = values[event]
            window['TRANSLATE_BAR'].update(percent)

        if event == '-TRANSLATE_FINISHED-':
            sg.popup('Translation completed successfully!')
            window['TRANSLATE_BAR'].update(0)

    window.close()

def translate_subtitles_thread(path_to_content, window):
    translated_content, lang = translate_subtitles(path_to_content, window=window)
    save_translated_subtitles(translated_content, path_to_content, lang)
    window.write_event_value('-TRANSLATE_FINISHED-', '')

if __name__ == '__main__':
    main()
