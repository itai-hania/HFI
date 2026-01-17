# HFI Implementation Plan - Simplified Architecture

## Phase 1: Project Setup ⏱️ ~30 minutes

### Step 1.1: Create Directory Structure
```bash
cd /Users/itayy16/CursorProjects/HFI
mkdir -p src/{scraper,processor,dashboard,common}
mkdir -p data/{media,session}
mkdir -p config
mkdir -p k8s
```

### Step 1.2: Create Base Configuration Files

**File: `.env`**
```bash
# X (Twitter) Credentials
X_USERNAME=your_burner_account@email.com
X_PASSWORD=your_password

# OpenAI API
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=sqlite:///data/hfi.db

# Redis (if using)
REDIS_URL=redis://localhost:6379/0
```

**File: `config/glossary.json`**
```json
{
  "Short Squeeze": "סקוויז שורט",
  "Bear Market": "שוק דובי",
  "Bull Market": "שוק שורי",
  "IPO": "הנפקה ראשונית",
  "Startup": "סטארטאפ",
  "VC": "הון סיכון",
  "Fintech": "פינטק",
  "Blockchain": "בלוקצ'יין",
  "API": "ממשק תכנות",
  "Revenue": "הכנסות"
}
```

**File: `config/style.txt`**
```
[Paste 5-10 examples of your best Hebrew tweets here]

Example:
🚨 עדכון טק: OpenAI מכריזה על GPT-5
הדבר הבא בתעשייה כבר כאן, וזה משנה הכל.
קראו למה המודל החדש הוא game changer 👇

[Your actual tweet examples...]
```

---

## Phase 2: Shared Database Models ⏱️ ~20 minutes

### Step 2.1: Create SQLAlchemy Models

**Prompt for AI Agent (Cursor/Windsurf):**
```
Create src/common/models.py with SQLAlchemy models for SQLite.

Requirements:
1. Table: tweets
   - id (Primary Key)
   - source_url (String) - Original X post URL
   - original_text (Text) - English content
   - hebrew_draft (Text) - Translated Hebrew
   - media_url (String) - Video/image URL if exists
   - media_path (String) - Local downloaded file path
   - trend_topic (String) - Which trend this relates to
   - status (Enum: 'pending', 'processed', 'approved', 'published')
   - created_at (DateTime)
   - updated_at (DateTime)

2. Table: trends
   - id (Primary Key)
   - title (String) - Trend name
   - description (Text) - What's trending
   - source (String) - 'X' or 'Reuters' or 'TechCrunch'
   - discovered_at (DateTime)

3. Include Base class and engine setup for SQLite
4. Add helper function create_tables()
```

**File: `src/common/models.py`**
```python
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import enum
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/hfi.db')

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

class TweetStatus(enum.Enum):
    pending = "pending"
    processed = "processed"
    approved = "approved"
    published = "published"

class Tweet(Base):
    __tablename__ = 'tweets'

    id = Column(Integer, primary_key=True)
    source_url = Column(String)
    original_text = Column(Text)
    hebrew_draft = Column(Text)
    media_url = Column(String, nullable=True)
    media_path = Column(String, nullable=True)
    trend_topic = Column(String, nullable=True)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Trend(Base):
    __tablename__ = 'trends'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(Text)
    source = Column(String)  # 'X', 'Reuters', 'TechCrunch'
    discovered_at = Column(DateTime, default=datetime.utcnow)

def create_tables():
    Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## Phase 3: Scraper Service ⏱️ ~2-3 hours

### Step 3.1: Scraper Base Code

**Prompt for AI Agent:**
```
Create src/scraper/scraper.py using Playwright for X (Twitter) scraping.

Requirements:
1. Class TwitterScraper with async methods
2. Session persistence:
   - Check for data/session/storage_state.json
   - If missing, do interactive login (headful mode, pause for user)
   - Save session after login
3. Method get_trending_topics():
   - Navigate to https://x.com/explore/tabs/trending
   - Extract top 10 trending topics
   - Return list of dicts: [{"title": "...", "description": "..."}]
4. Method get_tweet_content(url):
   - Navigate to tweet URL
   - Extract tweet text (use selector: [data-testid="tweetText"])
   - Set up network listener for video (.m3u8 URLs)
   - Return: {"text": "...", "media_url": "..." or None}
5. Use fake_useragent and disable navigator.webdriver
6. Random delays (2-5 seconds) between actions
```

**File: `src/scraper/requirements.txt`**
```
playwright==1.40.0
fake-useragent==1.5.1
python-dotenv==1.0.0
sqlalchemy==2.0.25
```

**File: `src/scraper/Dockerfile`**
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Install browsers (already in base image, but ensure)
RUN playwright install chromium

CMD ["python", "main.py"]
```

### Step 3.2: Main Scraper Entry Point

**File: `src/scraper/main.py`**
```python
import asyncio
import sys
sys.path.append('..')  # Access common modules

from scraper import TwitterScraper
from common.models import create_tables, SessionLocal, Tweet, Trend

async def main():
    # Ensure DB exists
    create_tables()

    scraper = TwitterScraper()

    # Step 1: Login (if needed)
    await scraper.ensure_logged_in()

    # Step 2: Get trending topics
    print("🔍 Fetching trending topics...")
    trends = await scraper.get_trending_topics()

    db = SessionLocal()
    for trend in trends[:5]:  # Top 5 only
        # Save to DB
        db_trend = Trend(
            title=trend['title'],
            description=trend.get('description', ''),
            source='X'
        )
        db.add(db_trend)
        print(f"✅ Trend: {trend['title']}")

    db.commit()

    # Step 3: Get top tweets from first trend (example)
    # You can expand this to scrape tweets related to each trend

    db.close()
    await scraper.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Phase 4: Processor Service ⏱️ ~2-3 hours

### Step 4.1: Translation + Media Download

**Prompt for AI Agent:**
```
Create src/processor/processor.py for content processing.

Requirements:
1. Function translate_and_rewrite(text, glossary, style_examples):
   - Use OpenAI GPT-4o API
   - System prompt: "You are a Hebrew financial analyst. Translate and rewrite this in the provided style. Use these term translations: {glossary}"
   - Include style examples in prompt
   - Return Hebrew text
2. Function download_media(media_url, output_path):
   - If URL ends with .m3u8 (HLS video):
     - Use yt-dlp to download: subprocess.run(['yt-dlp', media_url, '-o', output_path])
   - If URL is image (.jpg, .png):
     - Use requests to download
   - Return final file path
3. Function process_pending_tweets():
   - Query DB for tweets with status='pending'
   - For each:
     - Translate text
     - Download media if exists
     - Update DB with hebrew_draft, media_path, status='processed'
```

**File: `src/processor/requirements.txt`**
```
openai==1.10.0
sqlalchemy==2.0.25
python-dotenv==1.0.0
requests==2.31.0
yt-dlp==2024.1.1
```

**File: `src/processor/Dockerfile`**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install ffmpeg and curl (needed for yt-dlp)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### Step 4.2: Simple Queue System (Without Celery)

**For simplicity, we'll use a polling system instead of Celery:**

**File: `src/processor/main.py`**
```python
import time
import sys
sys.path.append('..')

from processor import process_pending_tweets

def main():
    print("🧠 Processor service started...")
    while True:
        print("🔄 Checking for pending tweets...")
        processed = process_pending_tweets()
        print(f"✅ Processed {processed} tweets")
        time.sleep(30)  # Check every 30 seconds

if __name__ == "__main__":
    main()
```

---

## Phase 5: Dashboard (Streamlit) ⏱️ ~1-2 hours

**Prompt for AI Agent:**
```
Create src/dashboard/app.py - a Streamlit dashboard.

Requirements:
1. Title: "Hebrew FinTech Informant (HFI) Dashboard"
2. Sidebar:
   - Filter by status (Pending/Processed/Approved)
   - Refresh button
3. Main area:
   - Display tweets as expandable cards
   - For each tweet:
     - Show original English text (read-only)
     - Show Hebrew draft (editable text area)
     - If media_path exists, show video/image
     - Button "Approve" → Updates status to 'approved'
     - Button "Delete"
4. Use SQLAlchemy to query from SQLite
5. Auto-refresh every 30 seconds (st.rerun)
```

**File: `src/dashboard/requirements.txt`**
```
streamlit==1.30.0
sqlalchemy==2.0.25
python-dotenv==1.0.0
```

**File: `src/dashboard/Dockerfile`**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## Phase 6: Docker Compose (Local Dev) ⏱️ ~30 min

**File: `docker-compose.yml`**
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  scraper:
    build: ./src/scraper
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    depends_on:
      - redis
    # Run manually or via cron, not continuously
    command: /bin/bash -c "echo 'Scraper ready. Run manually.'; tail -f /dev/null"

  processor:
    build: ./src/processor
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    depends_on:
      - redis
    restart: unless-stopped

  dashboard:
    build: ./src/dashboard
    env_file: .env
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
    depends_on:
      - processor
    restart: unless-stopped

volumes:
  redis_data:
```

**Usage:**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Run scraper manually
docker-compose exec scraper python main.py

# Access dashboard
open http://localhost:8501
```

---

## Phase 7: K3s Deployment ⏱️ ~1-2 hours

### Step 7.1: Install K3s
```bash
# Install K3s
curl -sfL https://get.k3s.io | sh -

# Copy kubeconfig
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chmod 600 ~/.kube/config

# Test
kubectl get nodes
```

### Step 7.2: Create K8s Manifests

**File: `k8s/namespace.yaml`**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: hfi-system
```

**File: `k8s/secrets.yaml`** (Don't commit!)
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: hfi-secrets
  namespace: hfi-system
type: Opaque
stringData:
  X_USERNAME: "your_email"
  X_PASSWORD: "your_password"
  OPENAI_API_KEY: "sk-..."
```

**File: `k8s/pvc.yaml`**
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: hfi-data-pvc
  namespace: hfi-system
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: local-path  # K3s default
```

**File: `k8s/deployment-dashboard.yaml`**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hfi-dashboard
  namespace: hfi-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hfi-dashboard
  template:
    metadata:
      labels:
        app: hfi-dashboard
    spec:
      containers:
      - name: dashboard
        image: hfi-dashboard:latest
        imagePullPolicy: Never  # Use local image
        ports:
        - containerPort: 8501
        envFrom:
        - secretRef:
            name: hfi-secrets
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: hfi-data-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: hfi-dashboard
  namespace: hfi-system
spec:
  type: NodePort
  ports:
  - port: 8501
    targetPort: 8501
    nodePort: 30080
  selector:
    app: hfi-dashboard
```

**File: `k8s/cronjob-scraper.yaml`**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: hfi-scraper
  namespace: hfi-system
spec:
  schedule: "*/30 * * * *"  # Every 30 minutes
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: scraper
            image: hfi-scraper:latest
            imagePullPolicy: Never
            envFrom:
            - secretRef:
                name: hfi-secrets
            volumeMounts:
            - name: data
              mountPath: /app/data
          restartPolicy: OnFailure
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: hfi-data-pvc
```

**Deploy:**
```bash
# Build images locally
docker build -t hfi-scraper:latest ./src/scraper
docker build -t hfi-processor:latest ./src/processor
docker build -t hfi-dashboard:latest ./src/dashboard

# Import to K3s
sudo k3s ctr images import hfi-scraper:latest
sudo k3s ctr images import hfi-processor:latest
sudo k3s ctr images import hfi-dashboard:latest

# Apply manifests
kubectl apply -f k8s/

# Check status
kubectl get pods -n hfi-system

# Access dashboard
open http://localhost:30080
```

---

## 🎯 Execution Order

### Week 1: Local Development
1. **Day 1:** Setup + Database models + Scraper basic structure
2. **Day 2:** Complete Scraper (X login, trending, tweet fetch)
3. **Day 3:** Processor (Translation + Media download)
4. **Day 4:** Dashboard UI
5. **Day 5:** Docker Compose integration + Testing

### Week 2: K8s Deployment
6. **Day 6-7:** K3s setup + Manifests + Deploy

---

## 🚀 Next Steps

Ready to start? I can help you with:

1. **Generate the exact code** for any service (just ask "write the scraper code")
2. **Debug issues** as they arise
3. **Optimize performance** once working
4. **Add features** (auto-posting, scheduling, analytics)

Which phase do you want to tackle first? I recommend starting with **Phase 2 (Database models)** since everything depends on it.
