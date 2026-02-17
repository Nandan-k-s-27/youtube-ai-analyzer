# 🎬 YouTube AI Analyzer

Convert YouTube videos into concise summaries, mind maps, and quizzes using Gemini + Flask.

## Features

- AI summary generation with adjustable length (10% to 50%)
- Mind map generation in Mermaid format
- Quiz generation from transcript content
- Transcript-first pipeline with audio fallback
- SQLite cache with TTL-based cleanup
- Real-time processing updates with Socket.IO
- Chrome extension support

## Tech Stack

- Python, Flask, Flask-SocketIO
- Google Gemini API
- yt-dlp, youtube-transcript-api, SpeechRecognition
- HTML/CSS/JavaScript + Mermaid

## Local Setup

### 1) Prerequisites

- Python 3.8+
- FFmpeg installed and available in PATH (recommended)
- Gemini API key: https://aistudio.google.com/apikey

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment

Create a `.env` file in project root:

```env
GEMINI_API_KEY=your_api_key_here
FLASK_DEBUG=false
PORT=5000
SECRET_KEY=your_secret_key
```

Optional cache tuning:

```env
CACHE_TTL_DAYS=7
CACHE_MAX_ENTRIES=500
CACHE_MAX_SIZE_MB=100
```

### 4) Run

```bash
python main.py
```

Open: http://127.0.0.1:5000

## Chrome Extension (Optional)

1. Open `chrome://extensions/`
2. Enable Developer mode
3. Click Load unpacked
4. Select the `chrome-extension` folder

## API Example

```python
import requests

response = requests.post("http://127.0.0.1:5000/api/process", json={
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "percentage": 25
})

print(response.json()["summary"])
```

## Cache Utilities

```bash
python manage_cache.py
python reset_cache.py
```

## Screenshots

### Web App

![Landing page (Light)](Screen_shots/Landing_page_light_mode.png)
![Landing page (Dark)](Screen_shots/Landing_page_dark_mode.png)
![Processing page](Screen_shots/Video_Processing_Page.png)
![Summary](Screen_shots/Summary.png)
![Mind map](Screen_shots/Mind_Map.png)
![Quiz](Screen_shots/Quiz.png)

### Chrome Extension

![Chrome extension](Screen_shots/Chrome_extension.png)
![Summary using extension](Screen_shots/summary_using_chrome_extension.png)

## Project Structure

```text
videotext/
├── main.py
├── video.py
├── cache_manager.py
├── manage_cache.py
├── reset_cache.py
├── requirements.txt
├── templates/
├── static/
├── chrome-extension/
└── Screen_shots/
```

## License

MIT License. See [LICENSE](LICENSE).
