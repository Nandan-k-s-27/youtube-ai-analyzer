"""Video Processing Module

Handles YouTube video processing including:
- Transcript extraction (auto-captions + manual subtitles)
- Audio fallback processing
- AI summarization with Gemini models
- Mind map generation
- Quiz question generation
- Intelligent caching
"""
import os
import re
import time
import json
import logging
import shutil
from typing import Dict, Optional, Callable, List
from urllib.parse import urlparse, parse_qs
from cache_manager import CacheManager

logger = logging.getLogger(__name__)

# ── Gemini Model Fallback Chain ──────────────────────────────────────────────
# Only models validated as available for the current API key + SDK version
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
]

MAX_RETRIES_PER_MODEL = 1
RETRY_DELAY = 60  # seconds - increased for rate limits


class VideoProcessor:
    def __init__(self):
        self.audio_path = "./temp_audio"
        self.chunks_path = "./temp_audio/chunks"
        self.cache = CacheManager()
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self.ffmpeg_available = self._configure_ffmpeg()

    def _configure_ffmpeg(self) -> bool:
        """Detect and configure ffmpeg/ffprobe paths for yt-dlp and pydub."""
        ffmpeg_candidates = [
            os.getenv("FFMPEG_BINARY"),
            "/opt/render/project/src/.render/ffmpeg/ffmpeg",
            shutil.which("ffmpeg"),
        ]
        ffprobe_candidates = [
            os.getenv("FFPROBE_BINARY"),
            "/opt/render/project/src/.render/ffmpeg/ffprobe",
            shutil.which("ffprobe"),
        ]

        self.ffmpeg_path = next((path for path in ffmpeg_candidates if path and os.path.exists(path)), None)
        self.ffprobe_path = next((path for path in ffprobe_candidates if path and os.path.exists(path)), None)

        if not self.ffmpeg_path:
            logger.warning(
                "FFmpeg not found. Audio fallback may fail. "
                "Install ffmpeg or configure Render build to include it."
            )
            return False

        os.environ["FFMPEG_BINARY"] = self.ffmpeg_path
        if self.ffprobe_path:
            os.environ["FFPROBE_BINARY"] = self.ffprobe_path

        try:
            from pydub import AudioSegment
            AudioSegment.converter = self.ffmpeg_path
            if self.ffprobe_path:
                AudioSegment.ffprobe = self.ffprobe_path
        except Exception as exc:
            logger.info("Pydub ffmpeg wiring skipped: %s", exc)

        logger.info("FFmpeg configured: %s", self.ffmpeg_path)
        return True

    def _is_ffmpeg_missing_error(self, error_text: str) -> bool:
        text = (error_text or "").lower()
        return (
            "ffmpeg" in text
            and (
                "not found" in text
                or "is not installed" in text
                or "postprocessing" in text
                or "ffmpegextractaudio" in text
            )
        )

    # ── URL Parsing ──────────────────────────────────────────────────────

    def get_video_id(self, url: str) -> str:
        parsed = urlparse(url)
        if 'youtu.be' in parsed.netloc:
            return parsed.path.strip('/')
        elif 'youtube.com' in parsed.netloc:
            query = parse_qs(parsed.query)
            video_id = query.get('v', [None])[0]
            if video_id:
                return video_id
        raise Exception("Invalid YouTube URL")

    # ── Metadata ─────────────────────────────────────────────────────────

    def get_video_metadata(self, video_id: str) -> Dict:
        try:
            import yt_dlp

            url = f"https://www.youtube.com/watch?v={video_id}"
            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                metadata = {
                    'title': info.get('title', ''),
                    'description': info.get('description', ''),
                    'tags': info.get('tags', []),
                    'duration': info.get('duration', 0),
                    'channel': info.get('channel', ''),
                    'upload_date': info.get('upload_date', ''),
                    'view_count': info.get('view_count', 0),
                }
                logger.info("Metadata fetched: %s", metadata['title'])
                return metadata

        except Exception as e:
            logger.error("Error fetching metadata: %s", e)
            return {'title': '', 'description': '', 'tags': []}

    # ── Quick Summary (LOCAL — no API call) ────────────────────────────

    def generate_quick_summary(self, metadata: Dict) -> str:
        """Build quick summary purely from metadata — zero API calls."""
        title = metadata.get('title', 'Unknown Video')
        description = metadata.get('description', '')
        channel = metadata.get('channel', '')
        duration = metadata.get('duration', 0)

        parts = []
        if title:
            parts.append(f'This video titled "{title}"')
        if channel:
            parts.append(f"by {channel}")
        if duration:
            mins = duration // 60
            secs = duration % 60
            parts.append(f"({mins}m {secs}s)")

        summary = ' '.join(parts) + '.'

        # Add first 2 sentences of description
        if description:
            sentences = re.split(r'(?<=[.!?])\s+', description.strip())
            first_two = ' '.join(sentences[:2]).strip()
            if first_two and len(first_two) > 20:
                summary += ' ' + first_two

        return summary

    # ── Transcript ───────────────────────────────────────────────────────

    def get_transcript(self, video_id: str) -> Optional[str]:
        try:
            import yt_dlp
            import json
            import requests

            url = f"https://www.youtube.com/watch?v={video_id}"
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitlesformat': 'json3',
                'subtitleslangs': ['en', 'en-US', 'en-GB'],
                'quiet': True,
                'no_warnings': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                subtitles = info.get('subtitles', {})
                auto_captions = info.get('automatic_captions', {})

                sub_data = None
                for lang in ['en', 'en-US', 'en-GB']:
                    if lang in subtitles:
                        sub_data = subtitles[lang]
                        break
                    elif lang in auto_captions:
                        sub_data = auto_captions[lang]
                        break

                if not sub_data:
                    return None

                json3_url = None
                for fmt in sub_data:
                    if fmt.get('ext') == 'json3':
                        json3_url = fmt.get('url')
                        break
                if not json3_url:
                    for fmt in sub_data:
                        if fmt.get('url'):
                            json3_url = fmt.get('url')
                            break
                if not json3_url:
                    return None

                response = requests.get(json3_url)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        texts = []
                        for event in data.get('events', []):
                            for seg in event.get('segs', []):
                                text = seg.get('utf8', '').strip()
                                if text and text != '\n':
                                    texts.append(text)
                        full_text = ' '.join(' '.join(texts).split())
                        if len(full_text) > 50:
                            logger.info("Transcript fetched: %d chars", len(full_text))
                            return full_text
                    except json.JSONDecodeError:
                        text = response.text
                        text = re.sub(r'\d{2}:\d{2}:\d{2}[.,]\d{3}.*?\n', '', text)
                        text = re.sub(r'<[^>]+>', '', text)
                        text = ' '.join(text.split())
                        if len(text) > 50:
                            return text
                return None

        except Exception as e:
            logger.warning("Could not fetch transcript: %s", e)
            return None

    # ── Audio Fallback ───────────────────────────────────────────────────

    def download_audio_only(self, url: str) -> str:
        try:
            import yt_dlp

            if not self.ffmpeg_available:
                raise Exception(
                    "FFmpeg is not available on the server, so audio fallback cannot run. "
                    "Deploy with render.yaml/build.sh so ffmpeg is installed."
                )

            os.makedirs(self.audio_path, exist_ok=True)
            output_path = os.path.join(self.audio_path, "audio.%(ext)s")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_path,
                'quiet': True,
                'noplaylist': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                'ffmpeg_location': os.path.dirname(self.ffmpeg_path) if self.ffmpeg_path else None,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return os.path.join(self.audio_path, "audio.wav")

        except Exception as e:
            raise Exception(f"Failed to download audio: {e}")

    def transcribe_audio(self, audio_path: str) -> str:
        try:
            import speech_recognition as sr
            from pydub import AudioSegment
            from pydub.silence import split_on_silence

            os.makedirs(self.chunks_path, exist_ok=True)
            recognizer = sr.Recognizer()
            sound = AudioSegment.from_wav(audio_path)

            chunks = split_on_silence(
                sound, min_silence_len=500,
                silence_thresh=sound.dBFS - 14, keep_silence=500
            )

            if len(chunks) > 50:
                chunk_size = len(chunks) // 50
                merged = []
                for i in range(0, len(chunks), chunk_size):
                    merged.append(sum(chunks[i:i + chunk_size], AudioSegment.empty()))
                chunks = merged

            full_text = ""
            for i, chunk in enumerate(chunks, 1):
                chunk_file = os.path.join(self.chunks_path, f"chunk{i}.wav")
                chunk.export(chunk_file, format="wav")
                with sr.AudioFile(chunk_file) as source:
                    try:
                        audio = recognizer.record(source)
                        full_text += recognizer.recognize_google(audio).capitalize() + '. '
                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        logger.error("Speech recognition error: %s", e)
                try:
                    os.remove(chunk_file)
                except OSError:
                    pass
            return full_text.strip()

        except Exception:
            raise

    # ── Gemini API Call with Multi-Model Fallback ────────────────────────

    def _list_available_models(self) -> List[str]:
        """List all available models for the current API key."""
        try:
            import google.generativeai as genai
            
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return []
            
            genai.configure(api_key=api_key)
            models = genai.list_models()
            
            # Filter to only generative models that support generateContent
            available = []
            for model in models:
                if 'generateContent' in model.supported_generation_methods:
                    available.append(model.name.replace('models/', ''))
            
            return available
        except Exception as e:
            logger.warning("Could not list available models: %s", e)
            return []

    def _call_gemini(self, prompt: str, models: List[str] = None) -> str:
        """
        Call Gemini API with multi-model fallback.
        Tries each model in the list. On rate-limit (429) or model error,
        falls back to the next model. Retries within each model for transient errors.
        """
        import google.generativeai as genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise Exception("GEMINI_API_KEY not found in environment")

        # Debug: show which key is active (masked for security)
        masked = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else api_key
        print(f"ACTIVE KEY: {masked}")

        genai.configure(api_key=api_key)

        if models is None:
            models = GEMINI_MODELS

        last_error = None

        for model_name in models:
            logger.info("Trying model: %s", model_name)

            for attempt in range(MAX_RETRIES_PER_MODEL):
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)

                    # Check if response has valid text
                    if response and response.text:
                        result = response.text.strip()
                        if result:
                            logger.info("Success with model %s (attempt %d)", model_name, attempt + 1)
                            return result

                    # Empty response — try again
                    logger.warning("Empty response from %s, attempt %d", model_name, attempt + 1)

                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    logger.warning("Error with %s (attempt %d): %s", model_name, attempt + 1, e)

                    # Rate limit — immediately try next model (don't wait on daily quota)
                    if '429' in str(e) or 'quota' in error_str or 'rate' in error_str or 'limit' in error_str:
                        logger.info("Rate/quota limit on %s, trying next model immediately...", model_name)
                        break  # Move to next model immediately

                    # Model not found — skip to next immediately
                    if '404' in str(e) or 'not found' in error_str or 'does not exist' in error_str:
                        logger.info("Model %s not available, trying next...", model_name)
                        break

                    # Other error — retry once, then move on
                    if attempt < MAX_RETRIES_PER_MODEL - 1:
                        time.sleep(5)
                        continue
                    break

        # All models exhausted
        available_models = self._list_available_models()
        error_msg = f"All Gemini models failed. Last error: {last_error}."
        
        if available_models:
            error_msg += f"\n\nAvailable models for your API key: {', '.join(available_models)}"
            error_msg += "\n\nTip: Update GEMINI_MODELS list in video.py to use one of the available models."
        else:
            error_msg += "\n\nCould not list available models. Please check your API key at https://aistudio.google.com/apikey"
        
        raise Exception(error_msg)

    # ── Mind Map Generation ──────────────────────────────────────────────

    def _sanitize_mindmap_label(self, value: str, max_len: int = 38) -> str:
        """Sanitize a label so Mermaid mindmap parsing stays stable."""
        cleaned = re.sub(r'[`"\'\[\]{}()<>|]', ' ', value or '')
        cleaned = re.sub(r'[:;,.!?/\\]+', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if not cleaned:
            return "Topic"
        if len(cleaned) > max_len:
            cleaned = cleaned[:max_len].rsplit(' ', 1)[0] or cleaned[:max_len]
        return cleaned

    def _build_fallback_mindmap(self, title: str) -> str:
        """Always-valid minimal fallback mindmap."""
        safe_title = self._sanitize_mindmap_label(title, 30)
        return (
            "mindmap\n"
            f"  root(({safe_title}))\n"
            "    Overview\n"
            "      Main ideas\n"
            "      Key details\n"
            "    Takeaways\n"
            "      Important points\n"
            "      Action items"
        )

    def _normalize_mindmap_output(self, raw: str, title: str) -> str:
        """
        Normalize model output into safe Mermaid mindmap syntax.
        Falls back to a guaranteed-valid map if structure is unusable.
        """
        if not raw:
            return self._build_fallback_mindmap(title)

        text = raw.strip()

        if text.startswith('```'):
            lines = text.split('\n')
            if lines and lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith('```'):
                lines = lines[:-1]
            text = '\n'.join(lines).strip()

        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if not lines:
            return self._build_fallback_mindmap(title)

        if lines[0].strip().lower() != 'mindmap':
            idx = next((i for i, line in enumerate(lines) if line.strip().lower() == 'mindmap'), -1)
            if idx >= 0:
                lines = lines[idx:]
            else:
                return self._build_fallback_mindmap(title)

        sanitized = ['mindmap']
        has_root = False

        for source_line in lines[1:]:
            line = source_line.replace('\t', '  ')
            indent = len(line) - len(line.lstrip(' '))
            level = max(1, min(3, indent // 2))
            raw_label = line.strip().lstrip('-*•0123456789. ').strip()
            if not raw_label:
                continue

            if raw_label.startswith('root(('):
                inner = raw_label[6:-2] if raw_label.endswith('))') else raw_label[6:]
                safe_root = self._sanitize_mindmap_label(inner, 30)
                sanitized.append(f"  root(({safe_root}))")
                has_root = True
                continue

            safe_label = self._sanitize_mindmap_label(raw_label)
            sanitized.append(('  ' * level) + safe_label)

        if not has_root:
            safe_title = self._sanitize_mindmap_label(title, 30)
            sanitized.insert(1, f"  root(({safe_title}))")

        if len(sanitized) < 4:
            return self._build_fallback_mindmap(title)

        return '\n'.join(sanitized)

    def generate_mindmap(self, text: str, title: str = "Video Concept") -> str:
        """Generate a Mermaid.js mind map from transcript using Gemini API."""
        
        # Truncate very long texts to stay within token limits
        max_chars = 20000
        truncated = text[:max_chars] if len(text) > max_chars else text

        prompt = f"""You are an expert at creating Mermaid.js mind maps.

Create a valid Mermaid mindmap diagram for the following text.

STRICT RULES:
1. Start with exactly "mindmap" on the first line
2. Second line must be root node: root((Topic Name))
3. Use 2 spaces for each indentation level
4. No special characters like (), [], {{}}, quotes in node text except for root
5. Keep all node labels SHORT (2-4 words)
6. Create 4-5 main branches
7. Each branch has 2-3 sub-items maximum
8. NO extra text, explanations, or code blocks
9. Only output the mindmap syntax

CORRECT EXAMPLE:
mindmap
  root((Video Summary))
    Main Concept 1
      Detail A
      Detail B
    Main Concept 2
      Detail C
      Detail D

TEXT:
{truncated}

OUTPUT (mindmap syntax only):"""

        result = self._call_gemini(prompt)
        result = self._normalize_mindmap_output(result, title)
        
        logger.info("Mind map generated: %d characters", len(result))
        return result

    # ── Summary Generation ───────────────────────────────────────────────

    def generate_summary(self, text: str, ratio: float = 0.25) -> str:
        """Generate summary using Gemini API with multi-model fallback."""
        original_words = len(text.split())
        target_words = max(50, int(original_words * ratio))

        # Truncate very long texts to stay within token limits
        max_chars = 25000
        truncated = text[:max_chars] if len(text) > max_chars else text

        if ratio <= 0.15:
            length_instruction = f"Create a very concise summary in approximately {target_words} words"
            detail_level = "Focus only on the most essential main points."
        elif ratio <= 0.25:
            length_instruction = f"Create a brief summary in approximately {target_words} words"
            detail_level = "Include the main points and key details."
        elif ratio <= 0.35:
            length_instruction = f"Create a moderate summary in approximately {target_words} words"
            detail_level = "Include main points, key details, and important supporting information."
        else:
            length_instruction = f"Create a detailed summary in approximately {target_words} words"
            detail_level = "Include main points, key details, supporting information, and relevant examples."

        prompt = f"""You are a professional content summarizer.

REQUIREMENTS:
- {length_instruction}
- {detail_level}
- Write in clear, coherent paragraphs
- Maintain the original meaning and context

TEXT:
{truncated}

SUMMARY:"""

        result = self._call_gemini(prompt)
        logger.info("Summary generated: %d words (target: %d)", len(result.split()), target_words)
        return result

    # ── Quiz Generation ─────────────────────────────────────────────────

    def _extract_json_payload(self, raw: str) -> Optional[Dict]:
        """Extract and parse JSON object from model output."""
        if not raw:
            return None

        cleaned = raw.strip()

        # Remove markdown fences if present
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```[a-zA-Z]*\n?', '', cleaned)
            cleaned = re.sub(r'\n?```$', '', cleaned)

        # Keep only JSON object content if extra text exists
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start == -1 or end == -1 or end <= start:
            return None

        cleaned = cleaned[start:end + 1]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _build_fallback_quiz(self, text: str, num_questions: int) -> List[Dict]:
        """Guaranteed fallback quiz when model JSON is invalid."""
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        stop_words = {
            'that', 'this', 'with', 'from', 'have', 'were', 'they', 'their',
            'about', 'there', 'would', 'could', 'should', 'which', 'when',
            'what', 'where', 'while', 'video', 'summary', 'content', 'into'
        }

        freq = {}
        for word in words:
            if word in stop_words:
                continue
            freq[word] = freq.get(word, 0) + 1

        ranked = [word for word, _ in sorted(freq.items(), key=lambda item: item[1], reverse=True)]
        keywords = ranked[: max(12, num_questions + 4)]

        if len(keywords) < 4:
            keywords = ['topic', 'concept', 'process', 'analysis', 'strategy', 'example']

        questions = []
        for index in range(num_questions):
            correct = keywords[index % len(keywords)].title()
            distractors = []
            cursor = (index + 1) % len(keywords)
            while len(distractors) < 3:
                candidate = keywords[cursor % len(keywords)].title()
                cursor += 1
                if candidate != correct and candidate not in distractors:
                    distractors.append(candidate)

            options = [correct] + distractors
            # Deterministic shuffle-like rotation to avoid always option A
            rotate = index % 4
            options = options[rotate:] + options[:rotate]
            correct_index = options.index(correct)

            questions.append({
                "question": f"Which topic is explicitly discussed in the video transcript? (Q{index + 1})",
                "options": options,
                "correct_index": correct_index,
            })

        return questions

    def generate_quiz_questions(self, text: str, title: str = "Video", num_questions: int = 5) -> List[Dict]:
        """Generate 5-10 MCQ questions from transcript content."""
        count = max(5, min(10, int(num_questions)))
        max_chars = 22000
        truncated = text[:max_chars] if len(text) > max_chars else text
        safe_title = self._sanitize_mindmap_label(title, 40)

        prompt = f"""You are an expert quiz creator.

Create exactly {count} multiple-choice questions from the transcript below.

STRICT OUTPUT REQUIREMENTS:
1) Return ONLY valid JSON (no markdown, no explanation).
2) Use this exact schema:
{{
  "questions": [
    {{
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "correct_index": 0
    }}
  ]
}}
3) Exactly 4 options per question.
4) correct_index must be integer 0..3.
5) Questions should be based on the transcript facts, not generic trivia.
6) Keep question text concise and clear.
7) Ensure only one correct answer.

Video title: {safe_title}
Transcript:
{truncated}
"""

        raw = self._call_gemini(prompt)
        payload = self._extract_json_payload(raw)

        if not payload or "questions" not in payload or not isinstance(payload["questions"], list):
            logger.warning("Quiz JSON parse failed. Using fallback quiz builder.")
            return self._build_fallback_quiz(truncated, count)

        validated = []
        for item in payload["questions"]:
            if not isinstance(item, dict):
                continue

            question = str(item.get("question", "")).strip()
            options = item.get("options", [])
            correct_index = item.get("correct_index", None)

            if not question or not isinstance(options, list) or len(options) != 4:
                continue

            clean_options = [str(option).strip() for option in options]
            if any(not option for option in clean_options):
                continue

            if not isinstance(correct_index, int) or correct_index < 0 or correct_index > 3:
                continue

            validated.append({
                "question": question,
                "options": clean_options,
                "correct_index": correct_index,
            })

            if len(validated) == count:
                break

        if len(validated) < count:
            logger.warning("Quiz had %d valid questions. Filling with fallback to reach %d.", len(validated), count)
            fallback_needed = count - len(validated)
            validated.extend(self._build_fallback_quiz(truncated, fallback_needed))

        return validated[:count]

    # ── Cleanup ──────────────────────────────────────────────────────────

    def cleanup_files(self):
        try:
            if os.path.exists(self.audio_path):
                shutil.rmtree(self.audio_path)
                logger.info("Temporary files cleaned up.")
        except Exception as e:
            logger.warning("Cleanup error: %s", e)

    # ── Main Processing Pipeline ─────────────────────────────────────────

    def process_video(self, url: str, method: str = 'abstractive',
                      percentage: float = 0.25,
                      progress_callback: Optional[Callable] = None) -> Dict:
        """
        Processing pipeline (only 1 Gemini API call with multi-model fallback):
        1. Check cache (0 API calls)
        2. Get metadata + local quick summary (0 API calls)
        3. Get transcript or audio fallback (0 API calls to Gemini)
        4. Generate full summary (1 API call with fallback chain)
        """
        try:
            video_id = self.get_video_id(url)
            logger.info("Processing video: %s", video_id)

            # Step 0: Check cache
            if progress_callback:
                progress_callback({'status': 'checking_cache', 'progress': 5})

            cached_result = self.cache.get_cached_summary(video_id, percentage)
            if cached_result:
                logger.info("Returning cached summary (0 API calls)")
                if progress_callback:
                    progress_callback({'status': 'complete', 'progress': 100, 'cached': True})
                return cached_result

            # Step 1: Metadata + local quick summary (no API call)
            if progress_callback:
                progress_callback({'status': 'fetching_metadata', 'progress': 10})

            metadata = self.get_video_metadata(video_id)
            title = metadata.get('title', 'Unknown Video')

            if progress_callback:
                progress_callback({'status': 'generating_quick_summary', 'progress': 20})

            quick_summary = self.generate_quick_summary(metadata)

            if progress_callback:
                progress_callback({
                    'status': 'quick_summary_ready',
                    'progress': 25,
                    'quick_summary': quick_summary,
                    'title': title,
                })

            # Step 2: Get transcript
            transcript_source = "transcript"
            if progress_callback:
                progress_callback({'status': 'fetching_transcript', 'progress': 35})

            text = self.get_transcript(video_id)

            # Step 3: Audio fallback if needed
            if not text or len(text.strip()) < 50:
                logger.info("No transcript, falling back to audio processing")
                transcript_source = "audio"

                try:
                    if progress_callback:
                        progress_callback({'status': 'downloading_audio', 'progress': 45})
                    audio_path = self.download_audio_only(url)

                    if progress_callback:
                        progress_callback({'status': 'transcribing_audio', 'progress': 65})
                    text = self.transcribe_audio(audio_path)
                    self.cleanup_files()
                except Exception as audio_exc:
                    audio_message = str(audio_exc)
                    if self._is_ffmpeg_missing_error(audio_message):
                        raise Exception(
                            "Could not extract transcript and audio fallback failed because FFmpeg is missing. "
                            "If you are on Render, use render.yaml/build.sh and redeploy."
                        )
                    raise Exception(f"Audio fallback failed: {audio_message}")

            if not text or len(text.strip()) < 20:
                raise Exception("Could not extract any text from the video")

            # Step 4: Generate full summary (ONLY API call — with model fallback)
            if progress_callback:
                progress_callback({'status': 'generating_full_summary', 'progress': 85})

            summary = self.generate_summary(text, percentage)

            result = {
                'text': text,
                'summary': summary,
                'method': method,
                'percentage': percentage * 100,
                'source': transcript_source,
                'title': title,
                'cached': False,
            }

            # Save to cache
            self.cache.save_summary(
                video_id=video_id, url=url, title=title,
                full_text=text, summary=summary,
                method=method, percentage=percentage,
                source=transcript_source,
            )

            if progress_callback:
                progress_callback({'status': 'complete', 'progress': 100})

            return result

        except Exception as e:
            logger.error("Error in process_video: %s", e)
            self.cleanup_files()
            if progress_callback:
                progress_callback({'status': 'error', 'error': str(e)})
            raise
