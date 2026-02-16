# 🚀 Production Deployment Guide

This guide covers deploying the YouTube AI Analyzer to production environments.

## 📋 Pre-Deployment Checklist

### ✅ Environment Configuration

1. **Environment Variables**
   - Copy `.env.example` to `.env`
   - Set `FLASK_DEBUG=false` (CRITICAL for production)
   - Set secure `SECRET_KEY` (use `python -c "import os; print(os.urandom(24).hex())"`)
   - Configure `GEMINI_API_KEY` with your production API key
   - Set `PORT` if not using default 5000

2. **Security Review**
   - ✅ API keys in `.env` file (not hardcoded)
   - ✅ `.env` file in `.gitignore`
   - ✅ Debug mode off by default
   - ✅ CORS configured appropriately
   - ✅ No sensitive data in logs

3. **Dependencies**
   ```bash
   pip install -r requirements.txt
   # Optional: flask-compress for gzip
   pip install -r requirements_optional.txt
   ```

---

## 🖥️ Deployment Options

### Option 1: Traditional Server (Gunicorn)

1. **Install Gunicorn** (already in requirements.txt)

2. **Create systemd service** (Linux):
   ```ini
   # /etc/systemd/system/youtube-ai.service
   [Unit]
   Description=YouTube AI Analyzer
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/var/www/youtube-ai-analyzer
   Environment="PATH=/var/www/youtube-ai-analyzer/venv/bin"
   ExecStart=/var/www/youtube-ai-analyzer/venv/bin/gunicorn \
       --worker-class eventlet \
       -w 1 \
       --bind 0.0.0.0:5000 \
       main:app
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. **Start service**:
   ```bash
   sudo systemctl enable youtube-ai
   sudo systemctl start youtube-ai
   ```

4. **Nginx reverse proxy** (recommended):
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

### Option 2: Docker Deployment

1. **Create Dockerfile**:
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   # Install system dependencies for audio processing
   RUN apt-get update && apt-get install -y \
       ffmpeg \
       && rm -rf /var/lib/apt/lists/*

   # Copy requirements and install Python dependencies
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy application code
   COPY . .

   # Create cache directory
   RUN mkdir -p cache

   # Expose port
   EXPOSE 5000

   # Run with gunicorn
   CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "main:app"]
   ```

2. **Create docker-compose.yml**:
   ```yaml
   version: '3.8'
   services:
     web:
       build: .
       ports:
         - "5000:5000"
       env_file:
         - .env
       volumes:
         - ./cache:/app/cache
       restart: unless-stopped
   ```

3. **Deploy**:
   ```bash
   docker-compose up -d
   ```

### Option 3: Cloud Platforms

#### Heroku
```bash
# Install Heroku CLI, then:
heroku create your-app-name
heroku config:set GEMINI_API_KEY=your_key
heroku config:set FLASK_DEBUG=false
git push heroku main
```

#### Railway / Render
- Connect GitHub repository
- Set environment variables in dashboard
- Deploy automatically on push

#### AWS EC2 / DigitalOcean
- Use Option 1 (Gunicorn + systemd)
- Configure security groups/firewall
- Point domain to server IP

---

## 🔌 Chrome Extension Configuration

The extension currently uses `localhost:5000`. For production:

### Option A: Self-Hosted Server

1. **Update API URLs** in:
   - `chrome-extension/popup.js` → `API_BASE`
   - `chrome-extension/content.js` → `API_BASE`
   - `chrome-extension/background.js` → `API_BASE`
   
   Change from:
   ```javascript
   const API_BASE = 'http://127.0.0.1:5000';
   ```
   
   To:
   ```javascript
   const API_BASE = 'https://yourdomain.com';
   ```

2. **Update `manifest.json` host_permissions**:
   ```json
   "host_permissions": [
     "https://yourdomain.com/*"
   ]
   ```

3. **Rebuild extension**:
   - Zip the `chrome-extension` folder
   - Upload to Chrome Web Store (or distribute as Developer Mode)

### Option B: Local-Only Installation

Keep localhost configuration and document that users must:
1. Run the Python server locally
2. Install extension in Developer Mode
3. Use extension only with local server running

---

## 🗄️ Database & Cache Management

### Cache Maintenance

The application uses SQLite for caching. No external database needed.

**Location**: `./cache/summaries.db`

**Maintenance Scripts**:
```bash
# View cache statistics
python manage_cache.py

# Clear old cache (30+ days)
python reset_cache.py

# Or via API:
curl -X POST http://localhost:5000/api/cache/clear \
  -H "Content-Type: application/json" \
  -d '{"days": 30}'
```

**Backup**:
```bash
# Simple file copy
cp cache/summaries.db cache/summaries_backup_$(date +%Y%m%d).db
```

---

## 📊 Monitoring & Logs

### Application Logs

The app uses Python's logging module. Configure log output:

```python
# In production, send logs to file:
import logging
logging.basicConfig(
    filename='/var/log/youtube-ai/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Health Check Endpoint

```bash
curl http://localhost:5000/health
# Response: {"status": "ok"}
```

Use this for monitoring tools (UptimeRobot, Pingdom, etc.)

### Metrics to Monitor

- Server uptime
- API response times
- Cache hit rate (via `/api/cache/stats`)
- Gemini API quota usage
- Disk space (cache can grow)

---

## 🔒 Security Best Practices

1. **API Key Protection**
   - Store in `.env` file only
   - Never commit `.env` to Git
   - Rotate keys periodically
   - Use `.env.example` template

2. **CORS Configuration**
   - Restrict to specific origins in production
   - Update `main.py` CORS settings:
     ```python
     from flask_cors import CORS
     CORS(app, origins=["https://yourdomain.com"])
     ```

3. **Rate Limiting** (recommended)
   ```bash
   pip install Flask-Limiter
   ```
   ```python
   from flask_limiter import Limiter
   limiter = Limiter(app, key_func=lambda: request.remote_addr)
   
   @app.route("/api/process")
   @limiter.limit("10 per hour")
   def process_video():
       ...
   ```

4. **HTTPS Only**
   - Use Nginx/Apache with SSL certificate
   - Free SSL with Let's Encrypt (certbot)
   - Redirect HTTP → HTTPS

5. **Input Validation**
   - Already validated in code
   - Consider additional sanitization for user inputs

---

## 🧪 Testing Before Deployment

```bash
# 1. Run with production settings locally
export FLASK_DEBUG=false
python main.py

# 2. Test all endpoints
curl http://localhost:5000/health
curl -X POST http://localhost:5000/api/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "percentage": 25}'

# 3. Test cache functionality
python manage_cache.py

# 4. Check logs for errors
tail -f logs/app.log
```

---

## 🔄 Continuous Deployment

### GitHub Actions Example

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Deploy to server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /var/www/youtube-ai-analyzer
            git pull
            source venv/bin/activate
            pip install -r requirements.txt
            sudo systemctl restart youtube-ai
```

---

## 📝 Post-Deployment Checklist

- [ ] Server running without errors
- [ ] Health check endpoint responds
- [ ] Can process a YouTube video successfully
- [ ] Cache is working (check stats endpoint)
- [ ] Logs are being written correctly
- [ ] Chrome extension connects (if applicable)
- [ ] HTTPS configured (if public)
- [ ] Backups configured
- [ ] Monitoring alerts set up

---

## 🆘 Troubleshooting

### Issue: "GEMINI_API_KEY not found"
**Solution**: Check `.env` file exists and is loaded. Verify environment variables with `echo $GEMINI_API_KEY`

### Issue: WebSocket connection failed
**Solution**: 
- Ensure proxy passes WebSocket upgrade headers (see Nginx config)
- Check firewall allows connections
- Verify `flask-socketio` and `eventlet` installed

### Issue: Cache growing too large
**Solution**: 
- Run `python reset_cache.py` to clear old entries
- Set up cron job for automatic cleanup:
  ```bash
  # Daily cache cleanup (entries older than 30 days)
  0 2 * * * cd /var/www/youtube-ai-analyzer && python reset_cache.py
  ```

### Issue: High memory usage
**Solution**: 
- Gunicorn workers: Use `-w 1` (single worker due to eventlet)
- Monitor with `htop` or cloud platform metrics
- Consider increasing server resources

---

## 📚 Additional Resources

- [Flask Deployment Documentation](https://flask.palletsprojects.com/en/3.0.x/deploying/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)
- [Let's Encrypt SSL Setup](https://letsencrypt.org/getting-started/)

---

**Need help?** Open an issue on GitHub or check the [README.md](README.md) for contact information.
