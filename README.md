# 🎬 YouTube AI Analyzer

> **Transform YouTube videos into actionable insights with AI-powered analysis**

A comprehensive platform that leverages Google's Gemini AI to analyze YouTube videos and generate summaries, mind maps, and interactive quizzes — all with a beautiful, modern interface.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ Features

### 🤖 **AI-Powered Analysis**
- **Smart Summarization**: Generate concise summaries with adjustable length (10-50%)
- **Visual Mind Maps**: Automatic concept mapping using Mermaid.js
- **Interactive Quizzes**: AI-generated MCQ questions based on video content
- **Multi-Model Fallback**: Automatic failover between Gemini models for reliability

### 🚀 **Performance & UX**
- **Real-time Processing**: WebSocket-based progress updates
- **Intelligent Caching**: SQLite-powered cache with TTL management
- **Responsive Design**: Beautiful UI with dark/light theme support
- **Progressive Quiz**: One-question-at-a-time flow with auto-advance
- **Tabbed Interface**: Clean navigation between Summary/Mind Map/Quiz/Transcript

### 🔌 **Multi-Platform Support**
- **Web Application**: Full-featured Flask web app
- **Chrome Extension**: Summarize videos directly from YouTube
- **REST API**: JSON endpoints for external integrations

### 📊 **Advanced Features**
- Transcript extraction (auto-captions + manual subtitles)
- Audio fallback with speech recognition
- PDF export with mind map inclusion
- Cache management dashboard
- Real-time statistics

## 🎯 Technologies

**Backend:**
- Python 3.8+
- Flask + Flask-SocketIO
- Google Gemini AI
- yt-dlp for video processing
- SQLite for caching

**Frontend:**
- Modern HTML5/CSS3/JavaScript
- Mermaid.js for mind maps
- Socket.IO for real-time updates
- Responsive design with CSS variables

**Chrome Extension:**
- Manifest V3
- Content Script injection
- Background service worker

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Google Gemini API key ([Get one here](https://aistudio.google.com/apikey))

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/youtube-ai-analyzer.git
   cd youtube-ai-analyzer
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   # Create .env file with your API key
   echo "GEMINI_API_KEY=your_api_key_here" > .env
   ```

4. **Run the application:**
   ```bash
   python main.py
   ```

5. **Open your browser:**
   ```
   http://127.0.0.1:5000
   ```

## 📖 Usage

### Web Application

1. **Paste YouTube URL** into the input field
2. **Select summary length** (10-50%)
3. **Click "Generate Summary"**
4. **Explore tabs:**
   - 📝 **Summary**: AI-generated concise summary
   - 🧠 **Mind Map**: Visual concept mapping
   - 📊 **Quiz**: Interactive knowledge test
   - 📄 **Transcript**: Full video transcript

### Chrome Extension

1. Navigate to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" and select `chrome-extension` folder
4. Visit any YouTube video
5. Click the extension icon to summarize

### API Usage

```python
import requests

response = requests.post('http://127.0.0.1:5000/api/process', json={
    'url': 'https://youtube.com/watch?v=VIDEO_ID',
    'percentage': 25
})

result = response.json()
print(result['summary'])
```

## 🛠️ Configuration

### Environment Variables

```env
# Required
GEMINI_API_KEY=your_api_key_here

# Optional
FLASK_DEBUG=false
PORT=5000
SECRET_KEY=your_secret_key

# Cache Configuration
CACHE_TTL_DAYS=7
CACHE_MAX_ENTRIES=500
CACHE_MAX_SIZE_MB=100
```

### Cache Management

```bash
# View cache statistics
python manage_cache.py

# Clear old cache
python reset_cache.py

# Check available Gemini models
python check_models.py
```

## 📁 Project Structure

```
youtube-ai-analyzer/
├── main.py                 # Flask application entry point
├── video.py               # Video processing & AI logic
├── cache_manager.py       # Intelligent caching system
├── templates/             # HTML templates
│   ├── index.html        # Landing page
│   ├── processing.html   # Real-time processing view
│   └── result.html       # Results display
├── static/               # CSS, JS assets
│   ├── shared.css       # Design system
│   ├── mindmap.css      # Mind map styling
│   └── global.js        # Global JavaScript
├── chrome-extension/     # Browser extension
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js
│   ├── content.js
│   └── background.js
└── cache/               # SQLite database (auto-created)
```

## 🎨 Features in Detail

### AI Summarization
- Uses Google's latest Gemini models
- Adjustable compression ratio (10-50%)
- Maintains key points and context
- Fallback chain for reliability

### Mind Map Generation
- Automatic concept extraction
- Hierarchical topic organization
- Interactive SVG rendering
- Dark/light theme support
- Download as SVG

### Quiz System
- 5-10 AI-generated questions
- Multiple choice format (4 options)
- Progressive one-at-a-time display
- Instant feedback with color coding
- Score tracking
- Retry functionality

### Caching
- Hash-based cache keys
- Percentage-aware caching
- Automatic TTL cleanup
- Performance analytics
- Size monitoring

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt -r requirements_optional.txt

# Run with debug mode
export FLASK_DEBUG=true
python main.py
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Google Gemini AI](https://ai.google.dev/) for powerful language models
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube data extraction
- [Mermaid.js](https://mermaid.js.org/) for mind map rendering
- [Flask](https://flask.palletsprojects.com/) for the web framework

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/youtube-ai-analyzer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/youtube-ai-analyzer/discussions)

---

**Made with ❤️ using AI**
