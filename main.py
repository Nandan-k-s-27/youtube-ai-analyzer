"""YouTube AI Summarizer - Main Flask Application

A comprehensive YouTube video analysis platform featuring:
- Real-time AI-powered summarization
- Interactive mind map generation
- Transcript-based quiz system
- Advanced caching for performance
- Chrome extension support
"""
import os
import logging
from threading import Thread

from flask import Flask, jsonify, request, render_template, flash, redirect, url_for
from flask_socketio import SocketIO
from dotenv import load_dotenv

from video import VideoProcessor
from cache_manager import CacheManager

# ─── Configuration ──────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())

# Enable compression for better performance (optional - install flask-compress)
try:
    from flask_compress import Compress
    Compress(app)
    logger.info("✓ Response compression enabled")
except ImportError:
    logger.info("ℹ️  flask-compress not installed (optional for performance)")

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Shared instances
processor = VideoProcessor()
cache = CacheManager()

# Perform cleanup on startup
logger.info("🧹 Running startup cleanup...")
try:
    stats = cache.get_cache_stats()
    logger.info(f"📊 Cache: {stats['total_entries']} entries, {stats['database_size_mb']} MB")
except Exception as e:
    logger.warning(f"Could not get cache stats: {e}")


# ─── Page Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Landing page."""
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process_video():
    """Validate form & show real-time processing page."""
    url = request.form.get("url", "").strip()
    percentage = int(request.form.get("percentage", 25))

    if not url:
        flash("Please provide a YouTube URL", "error")
        return redirect(url_for("index"))

    if not url.startswith(("https://www.youtube.com/", "https://youtu.be/",
                           "http://www.youtube.com/",  "http://youtu.be/")):
        flash("Please provide a valid YouTube URL", "error")
        return redirect(url_for("index"))

    return render_template("processing.html", url=url, percentage=percentage)


# ─── WebSocket Events ───────────────────────────────────────────────────────────

@socketio.on("start_processing")
def handle_start_processing(data):
    """Kick off video processing in a background thread."""
    url = data.get("url")
    percentage = data.get("percentage", 25) / 100.0
    session_id = request.sid

    logger.info("WS start_processing  url=%s  sid=%s", url, session_id)

    def progress_callback(payload):
        socketio.emit("progress_update", payload, room=session_id)

    def _run():
        try:
            result = processor.process_video(
                url, percentage=percentage, progress_callback=progress_callback
            )
            socketio.emit("processing_complete", result, room=session_id)
        except Exception as exc:
            logger.error("Background processing error: %s", exc)
            socketio.emit("processing_error", {"error": str(exc)}, room=session_id)

    thread = Thread(target=_run, daemon=True)
    thread.start()


# ─── CORS for Chrome Extension ───────────────────────────────────────────────

@app.after_request
def add_cors_headers(response):
    """Allow requests from the Chrome extension."""
    origin = request.headers.get('Origin', '')
    if origin.startswith('chrome-extension://') or origin in ('http://127.0.0.1:5000', 'http://localhost:5000', ''):
        response.headers['Access-Control-Allow-Origin'] = origin or '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# ─── REST API ────────────────────────────────────────────────────────────────────

@app.route("/api/process", methods=["POST", "OPTIONS"])
def api_process_video():
    """Non-WebSocket JSON endpoint (also serves Chrome extension)."""
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    if not url:
        return jsonify({"error": "URL is required"}), 400
    try:
        percentage = data.get("percentage", 25) / 100.0
        result = processor.process_video(url, percentage=percentage)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/cache/stats", methods=["GET"])
def get_cache_stats():
    try:
        return jsonify(cache.get_cache_stats())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/cache/clear", methods=["POST"])
def clear_old_cache():
    try:
        days = (request.get_json(silent=True) or {}).get("days", 30)
        deleted = cache.clear_old_cache(days)
        return jsonify({"deleted": deleted, "message": f"Cleared {deleted} old entries"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/generate-mindmap", methods=["POST"])
def generate_mindmap():
    """Generate a mind map from transcript text."""
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        title = data.get("title", "Video Concept")
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        if len(text) < 50:
            return jsonify({"error": "Text too short to generate mind map"}), 400
        
        mindmap = processor.generate_mindmap(text, title)
        return jsonify({"mindmap": mindmap, "success": True})
    except Exception as exc:
        logger.error("Mind map generation error: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/generate-quiz", methods=["POST"])
def generate_quiz():
    """Generate 5-10 MCQ quiz questions based on transcript content."""
    try:
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        title = data.get("title", "Video")
        num_questions = int(data.get("num_questions", 5))

        if not text:
            return jsonify({"error": "Text is required"}), 400

        if len(text) < 120:
            return jsonify({"error": "Text too short to generate quiz"}), 400

        if num_questions < 5 or num_questions > 10:
            return jsonify({"error": "num_questions must be between 5 and 10"}), 400

        questions = processor.generate_quiz_questions(
            text=text,
            title=title,
            num_questions=num_questions,
        )

        return jsonify({
            "success": True,
            "questions": questions,
            "count": len(questions),
        })
    except Exception as exc:
        logger.error("Quiz generation error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ─── Health Check ────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ─── Entry Point ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("Starting server on http://127.0.0.1:%d  (debug=%s)", port, debug)
    socketio.run(app, debug=debug, host="127.0.0.1", port=port, allow_unsafe_werkzeug=True)