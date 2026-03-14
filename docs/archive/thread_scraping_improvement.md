# Thread Scraping Improvement Plan

**Created:** 2026-01-28
**Last Updated:** 2026-01-28
**Status:** Phase 1.1, 1.2, 1.3 Complete ✅ | Ready for Testing

---

## 🎯 Current Status

### ✅ Completed
- **Phase 1.1: Context-Aware Thread Translation** (2026-01-28)
  - Added `translate_thread_consolidated()` method to processor
  - Added `translate_thread_separate()` method to processor
  - Integrated auto-translate in dashboard scraping flow
  - Added "Auto-translate" checkbox to UI
  - Smart status management (PROCESSED when translated)
  - User feedback improvements

- **Phase 1.2: Thread Media Download Pipeline** (2026-01-28)
  - Added `media_paths` column to Tweet model (JSON storage)
  - Migration script auto-runs on database init
  - Integrated `download_thread_media()` in dashboard scraping
  - Media downloaded automatically during thread scrape
  - Tests added: `tests/test_thread_media.py`

- **Phase 1.3: Media Visibility in Dashboard** (2026-01-28)
  - Media indicators in queue list (🎥 for video, 🖼️ for photos)
  - Media count displayed next to each item
  - Media gallery in editor view with thumbnails
  - Handles missing files gracefully with error display

### 🔄 In Progress
- **Testing Phases 1.1-1.3** (Current)
  - Manual testing of consolidated translation
  - Testing media download with real threads
  - Verifying gallery display in editor

### 📋 Next Up
- **Phase 2.1: Thread Preview & Editing UI** (Pending)

---

## 🧪 Testing Results - Phase 1.1

### Test Environment
- **Date Tested:** _[Pending]_
- **Tester:** _[Your name]_
- **Dashboard Version:** Latest (2026-01-28)
- **OpenAI Model:** gpt-4o
- **Temperature:** 0.7

### Test Case 1: Consolidated Thread (Auto-Translate ON)
**Thread URL:** _[Add URL here]_
**Tweet Count:** _[X tweets]_
**Expected:** ONE flowing Hebrew post, no thread markers

**Results:**
- [ ] Translation completed successfully
- [ ] No "1/5, 2/5" markers in output
- [ ] No "---" separators in output
- [ ] Natural Hebrew paragraph structure
- [ ] All key information preserved
- [ ] Status = PROCESSED

**Hebrew Output:**
```
[Paste Hebrew translation here]
```

**Quality Rating:** _[1-5 stars]_
**Notes:** _[Any observations]_

---

### Test Case 2: Separate Tweets with Context (Auto-Translate ON)
**Thread URL:** _[Add URL here]_
**Tweet Count:** _[X tweets]_
**Expected:** X Hebrew tweets, each aware of previous context

**Results:**
- [ ] All tweets translated successfully
- [ ] No repetition across tweets
- [ ] Context continuity maintained
- [ ] Later tweets reference earlier content appropriately
- [ ] Status = PROCESSED for all

**Tweet 1 Hebrew:**
```
[Paste here]
```

**Tweet 2 Hebrew:**
```
[Paste here]
```

**Tweet 3 Hebrew:**
```
[Paste here]
```

**Quality Rating:** _[1-5 stars]_
**Context Awareness Rating:** _[1-5 stars]_
**Notes:** _[Any observations]_

---

### Test Case 3: Without Auto-Translate (Baseline)
**Thread URL:** _[Add URL here]_
**Expected:** Added as PENDING, no translation

**Results:**
- [ ] Thread added to queue
- [ ] Status = PENDING
- [ ] Hebrew draft empty
- [ ] Can translate manually later

**Notes:** _[Any observations]_

---

### Performance Metrics
**Consolidated Translation:**
- Scraping time: _[X seconds]_
- Translation time: _[X seconds]_
- Total time: _[X seconds]_

**Separate Translation:**
- Scraping time: _[X seconds]_
- Translation time: _[X seconds per tweet]_
- Total time: _[X seconds]_

**API Costs:**
- Tokens used (consolidated): _[X tokens]_
- Tokens used (separate): _[X tokens]_
- Estimated cost: _[$X]_

---

### Issues Found
1. _[List any bugs, errors, or unexpected behavior]_
2. _[...]_

### Improvements Needed
1. _[List any prompt tweaks or code changes needed]_
2. _[...]_

### Overall Assessment
**Phase 1.1 Status:** _[Pass / Needs Work / Fail]_

**Recommendation:**
- [ ] Move to Phase 1.2 (Media Download)
- [ ] Iterate on prompts (translation quality issues)
- [ ] Fix bugs before proceeding
- [ ] Other: _[specify]_

---

## 📝 Changelog

### 2026-01-28 - Phase 1.1 Implementation
**Added:**
- `TranslationService.translate_thread_consolidated()` - Translates entire thread as one flowing Hebrew narrative
- `TranslationService.translate_thread_separate()` - Translates each tweet with context from previous tweets
- Dashboard "Auto-translate" checkbox in thread scraping UI
- Context-aware translation integration in both consolidate and separate modes

**Changed:**
- Thread scraping now auto-translates during scraping (optional)
- Status set to PROCESSED when auto-translated (instead of PENDING)
- Success messages now indicate if translation occurred

**Technical Details:**
- Enhanced system prompts for narrative rewriting
- Context accumulation across tweets in separate mode
- Validation and retry logic preserved
- Backward compatible (auto-translate can be disabled)

**Testing Status:**
- Code implemented and ready for testing
- Manual testing required for quality assessment
- Need to verify Hebrew output has no thread markers
- Need to compare with old concatenation method

---

## Overview

This document outlines improvements to the HFI thread scraping functionality, covering translation quality, media handling, and user experience enhancements.

---

## Current State Analysis

### What's Working ✅
- Thread scraping from X (with author filtering)
- Basic consolidation (concatenates tweets with separators)
- Separate tweet mode (saves each tweet individually)
- Database models (Thread, Tweet tables)
- Media downloader exists (`MediaDownloader` class)

### Critical Issues ❌

1. **Translation Ignores Thread Context**
   - Problem: Each tweet translated independently, losing narrative flow
   - Current: Uses `translate_and_rewrite()` per tweet
   - Impact: Disjointed translations, repeated phrases, lost coherence

2. **No Media Download for Threads**
   - Problem: `download_thread_media()` method exists but never called
   - Current: Only single `media_url` field used
   - Impact: Thread media completely lost after scraping

3. **Zero Media Visibility in UI**
   - Problem: User quote: "Can't see anything related to download media on the UI"
   - Current: No indicators, no previews, no status
   - Impact: Users have no idea if media exists or was downloaded

4. **No Consolidated Narrative Rewrite**
   - Problem: Just joins tweets with `\n\n---\n\n`, not a flowing story
   - Current: Simple concatenation
   - Impact: Reads like separate tweets, not a cohesive post

5. **Single Media URL Limitation**
   - Problem: Database stores only ONE `media_url` per tweet
   - Current: `media_url` is a String field
   - Impact: Threads with multiple images/videos lose media

---

## User Requirements (From Q&A)

### Workflow
- **Choice per thread**: Both consolidate and separate options available
- **Auto-scrape + preview**: Scrape on paste, show preview before processing

### Translation
- **Context-aware**: Use full thread context for translation
- **Flowing narrative**: Consolidated threads rewritten as single cohesive Hebrew post
- **Preserve structure**: Keep thread markers/numbering if user wants

### Media
- **Download all media**: All images and videos from thread
- **Preserve association**: Track which media belongs to which tweet number
- **Visible status**: Show media count, download progress, thumbnails

### UX
- **Preview before processing**: See full thread structure after scraping
- **Edit thread structure**: Remove tweets, reorder, adjust before translation
- **Media gallery**: Visual display of all thread media

---

## Implementation Plan

### Phase 1: Core Translation & Media (Critical) 🔥

#### 1.1 Context-Aware Thread Translation

**Goal:** Use full thread context for translation, producing flowing Hebrew narrative.

**Changes Needed:**

**A. Processor (`processor.py`):**
```python
class TranslationService:
    def translate_thread_consolidated(self, tweets: List[Dict]) -> str:
        """
        Translate entire thread as one flowing narrative.

        Args:
            tweets: List of tweet dicts with 'text', 'author_handle', etc.

        Returns:
            Single flowing Hebrew post (no thread markers)
        """
        # Extract all text
        texts = [t['text'] for t in tweets if t.get('text')]

        # Combine into single context
        combined = "\n\n".join(texts)

        # Enhanced system prompt for narrative rewrite
        system_prompt = f"""You are translating a Twitter THREAD (not single tweet).

CRITICAL: Rewrite as a SINGLE FLOWING HEBREW POST:
- NO thread markers (1/5, 2/5, etc.)
- NO separators or breaks between original tweets
- Combine into ONE cohesive narrative
- Maintain all key information
- Use natural Hebrew paragraph structure
- Max 280 characters if possible, or natural break points

Original thread has {len(tweets)} tweets. Create ONE unified Hebrew post."""

        # Call OpenAI with enhanced prompt
        # ... (existing translation logic with new prompt)

    def translate_thread_separate(self, tweets: List[Dict]) -> List[str]:
        """
        Translate each tweet with context of previous tweets.

        Args:
            tweets: List of tweet dicts

        Returns:
            List of Hebrew translations (one per tweet)
        """
        results = []
        context = []

        for idx, tweet in enumerate(tweets):
            # Build context from previous tweets
            context_str = "\n".join(context) if context else ""

            system_prompt = f"""You are translating tweet {idx+1}/{len(tweets)} from a thread.

Previous tweets in thread:
{context_str}

Current tweet to translate:
{tweet['text']}

Translate to Hebrew while maintaining thread continuity."""

            # Translate with context
            translation = self.translate_and_rewrite(tweet['text'], system_prompt)
            results.append(translation)

            # Add to context for next tweet
            context.append(f"{idx+1}. {tweet['text']}")

        return results
```

**B. Dashboard (`app.py`):**
```python
def _render_acquire_section(db):
    # ... existing scraping code ...

    if add_to_queue:
        tweets_data = result.get('tweets', [])

        if consolidate and len(tweets_data) > 1:
            # NEW: Use context-aware translation
            with st.spinner("Translating as consolidated thread..."):
                from processor.processor import ProcessorConfig, TranslationService
                config = ProcessorConfig()
                translator = TranslationService(config)

                # Translate with full thread context
                hebrew_translation = translator.translate_thread_consolidated(tweets_data)

                # Combine original text for reference
                combined_original = "\n\n---\n\n".join([t.get('text', '') for t in tweets_data])

                # Download all media
                from processor.processor import MediaDownloader
                downloader = MediaDownloader()
                media_results = downloader.download_thread_media(result)

                # Store first media path (or JSON of all media)
                first_media_path = media_results[0]['local_path'] if media_results else None

                # Create tweet
                db.add(Tweet(
                    source_url=tweets_data[0].get('permalink', url),
                    original_text=combined_original,
                    hebrew_draft=hebrew_translation,  # Already translated!
                    status=TweetStatus.PROCESSED,  # Skip PENDING
                    media_path=first_media_path,
                    trend_topic=result.get('author_handle', '')
                ))
                db.commit()
```

**Files to Modify:**
- `src/processor/processor.py` (add methods)
- `src/dashboard/app.py` (hook up translation)

**Testing:**
- Scrape 3+ tweet thread
- Check Hebrew output is ONE flowing post
- Verify no "1/5, 2/5" markers
- Compare with old concatenated version

---

#### 1.2 Thread Media Download Pipeline

**Goal:** Download all media from threads and store paths.

**Changes Needed:**

**A. Database Schema Enhancement:**

**Option 1: JSON Array (Flexible)**
```python
# In models.py
class Tweet(Base):
    # Change from String to Text for JSON storage
    media_paths = Column(
        Text,
        nullable=True,
        comment="JSON array of media file paths: [{tweet_id, type, path}, ...]"
    )
```

**Option 2: Separate MediaFile Table (Normalized)**
```python
# In models.py
class MediaFile(Base):
    __tablename__ = 'media_files'

    id = Column(Integer, primary_key=True)
    tweet_id = Column(Integer, ForeignKey('tweets.id'), nullable=False)
    tweet_number = Column(Integer, nullable=True, comment="Position in thread (1-based)")
    media_type = Column(String(20), nullable=False)  # 'photo' or 'video'
    source_url = Column(String(1024), nullable=False)
    local_path = Column(String(512), nullable=True)
    download_status = Column(String(20), default='pending')  # pending/success/failed
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

**Recommendation:** Start with JSON array (simpler), migrate to separate table if needed.

**B. Migration Script:**
```python
# In models.py create_tables()
with engine.connect() as conn:
    try:
        # Add media_paths column as JSON
        conn.execute(
            text("ALTER TABLE tweets ADD COLUMN media_paths TEXT")
        )
        conn.commit()
        logger.info("Migration: added media_paths column")
    except Exception:
        pass  # Already exists
```

**C. Dashboard Integration:**
```python
# In app.py _render_acquire_section()
if consolidate and len(tweets_data) > 1:
    # Download all media
    from processor.processor import MediaDownloader
    downloader = MediaDownloader()

    with st.spinner("Downloading thread media..."):
        media_results = downloader.download_thread_media(result)

    # Store as JSON
    import json
    media_json = json.dumps(media_results) if media_results else None

    db.add(Tweet(
        # ... other fields ...
        media_paths=media_json,  # Store all media
        media_path=media_results[0]['local_path'] if media_results else None  # Backward compat
    ))
```

**Files to Modify:**
- `src/common/models.py` (add column + migration)
- `src/dashboard/app.py` (call download_thread_media)
- `src/processor/processor.py` (verify download_thread_media works)

**Testing:**
- Scrape thread with 2+ images
- Check `media_paths` JSON stored correctly
- Verify files exist in `data/media/images/`
- Test thread with video

---

#### 1.3 Media Visibility in Dashboard

**Goal:** Show media count, status, and thumbnails in UI.

**Changes Needed:**

**A. Queue List View (show media indicators):**
```python
# In app.py render_content_item()
def render_content_item(tweet, db):
    # ... existing code ...

    # NEW: Media indicator
    media_count = 0
    media_icon = ""

    if tweet.media_paths:
        import json
        try:
            media_list = json.loads(tweet.media_paths)
            media_count = len(media_list)

            # Icon based on media types
            has_video = any(m['type'] == 'video' for m in media_list)
            has_photo = any(m['type'] == 'photo' for m in media_list)

            if has_video:
                media_icon = "🎥"
            elif has_photo:
                media_icon = "🖼️"
        except:
            pass

    with col2:
        if media_count > 0:
            st.markdown(f"""
                <div style="font-size: 0.75rem; color: var(--accent-primary);">
                    {media_icon} {media_count} media
                </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("No media")
```

**B. Editor View (show media gallery):**
```python
# In app.py render_editor()
def render_editor(db, tweet_id):
    # ... existing code ...

    # NEW: Media gallery section
    if tweet.media_paths:
        st.markdown("---")
        st.markdown("### Thread Media")

        import json
        try:
            media_list = json.loads(tweet.media_paths)

            # Display in columns
            cols = st.columns(min(len(media_list), 4))

            for idx, media_item in enumerate(media_list):
                with cols[idx % 4]:
                    media_type = media_item.get('type', 'unknown')
                    local_path = media_item.get('local_path', '')
                    tweet_num = media_item.get('tweet_id', 'unknown')

                    if local_path and Path(local_path).exists():
                        if media_type == 'photo':
                            st.image(local_path, caption=f"Tweet {tweet_num}", use_container_width=True)
                        elif media_type == 'video':
                            st.video(local_path)
                    else:
                        st.caption(f"❌ {media_type} (missing)")

        except json.JSONDecodeError:
            st.error("Invalid media data")
```

**C. Preview During Scraping:**
```python
# In app.py _render_acquire_section()
if st.button("Scrape Thread", ...):
    # ... scraping code ...

    # Show preview
    with st.expander("📋 Thread Preview", expanded=True):
        st.write(f"**Author:** {result.get('author_handle')}")
        st.write(f"**Tweets:** {len(tweets_data)}")

        # Media summary
        total_media = sum(len(t.get('media', [])) for t in tweets_data)
        st.write(f"**Media:** {total_media} files")

        # Tweet list
        for idx, t in enumerate(tweets_data, 1):
            with st.container():
                media_icons = " ".join(["🖼️" if m['type']=='photo' else "🎥"
                                        for m in t.get('media', [])])
                st.markdown(f"**{idx}.** {t['text'][:80]}... {media_icons}")
```

**Files to Modify:**
- `src/dashboard/app.py` (all UI changes)

**Testing:**
- Scrape thread with media
- Check media indicators in queue list
- Open editor, verify thumbnails display
- Test missing media (delete file, check UI shows error)

---

### Phase 2: UX Enhancements (Medium Priority) 📊

#### 2.1 Thread Preview & Editing UI

**Goal:** Show preview after scraping, allow editing before processing.

**Implementation:**

**A. New Session State Management:**
```python
# In app.py
def _render_acquire_section(db):
    # Initialize preview state
    if 'thread_preview' not in st.session_state:
        st.session_state.thread_preview = None

    # After scraping
    if scrape_successful:
        st.session_state.thread_preview = {
            'url': url,
            'data': result,
            'tweets': tweets_data
        }
        st.rerun()
```

**B. Preview & Edit UI:**
```python
def render_thread_preview():
    """Show thread preview with editing capabilities."""
    preview = st.session_state.thread_preview

    st.markdown("## Thread Preview")

    # Summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tweets", len(preview['tweets']))
    with col2:
        total_media = sum(len(t.get('media', [])) for t in preview['tweets'])
        st.metric("Media", total_media)
    with col3:
        st.metric("Author", preview['data'].get('author_handle', 'Unknown'))

    st.markdown("---")

    # Tweet list with checkboxes and reorder buttons
    st.markdown("### Select Tweets to Include")

    selected_tweets = []

    for idx, tweet in enumerate(preview['tweets']):
        col1, col2, col3 = st.columns([1, 10, 1])

        with col1:
            include = st.checkbox("", value=True, key=f"tweet_include_{idx}")

        with col2:
            media_preview = ""
            if tweet.get('media'):
                media_preview = " | ".join([
                    "🖼️ Photo" if m['type']=='photo' else "🎥 Video"
                    for m in tweet['media']
                ])

            st.markdown(f"""
                <div style="padding: 0.5rem; background: var(--bg-secondary); border-radius: 8px;">
                    <strong>Tweet {idx+1}</strong><br/>
                    {tweet['text'][:120]}...<br/>
                    <small style="color: var(--text-muted);">{media_preview}</small>
                </div>
            """, unsafe_allow_html=True)

        with col3:
            # Reorder buttons (up/down)
            if idx > 0:
                if st.button("⬆️", key=f"up_{idx}"):
                    preview['tweets'][idx], preview['tweets'][idx-1] = \
                        preview['tweets'][idx-1], preview['tweets'][idx]
                    st.rerun()
            if idx < len(preview['tweets']) - 1:
                if st.button("⬇️", key=f"down_{idx}"):
                    preview['tweets'][idx], preview['tweets'][idx+1] = \
                        preview['tweets'][idx+1], preview['tweets'][idx]
                    st.rerun()

        if include:
            selected_tweets.append(tweet)

    st.markdown("---")

    # Action buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        consolidate_mode = st.checkbox("Consolidate", value=True)

    with col2:
        auto_translate = st.checkbox("Auto-translate", value=True)

    with col3:
        if st.button("➕ Add to Queue", type="primary"):
            # Process selected tweets
            process_thread_to_queue(db, selected_tweets, consolidate_mode, auto_translate)
            st.session_state.thread_preview = None
            st.success(f"Added {len(selected_tweets)} tweets to queue")
            time.sleep(1)
            st.rerun()

    with col4:
        if st.button("❌ Cancel"):
            st.session_state.thread_preview = None
            st.rerun()
```

**Files to Modify:**
- `src/dashboard/app.py` (add preview UI + session state)

**Testing:**
- Scrape thread, verify preview shows
- Uncheck tweets, verify only selected ones added
- Reorder tweets, verify order preserved
- Cancel, verify returns to normal UI

---

#### 2.2 Flowing Narrative Mode

**Goal:** GPT rewrites consolidated threads as single cohesive Hebrew post.

**Implementation:**

Already covered in Phase 1.1 with enhanced system prompt. Key additions:

**A. Add UI Toggle:**
```python
# In dashboard preview/options
narrative_mode = st.checkbox(
    "Flowing Narrative (recommended)",
    value=True,
    help="Rewrite as single cohesive post instead of concatenating tweets"
)
```

**B. Processor Logic:**
```python
# In processor.py
if narrative_mode:
    hebrew_text = translator.translate_thread_consolidated(tweets)
else:
    hebrew_text = "\n\n---\n\n".join([
        translator.translate_and_rewrite(t['text']) for t in tweets
    ])
```

**Testing:**
- Compare narrative mode ON vs OFF
- Verify narrative mode has no "---" separators
- Check for natural Hebrew flow
- Verify key info preserved

---

### Phase 3: Database & Architecture (Optional) 🏗️

#### 3.1 Separate MediaFile Table

**Goal:** Normalize media storage for better querying and management.

**When to implement:**
- If media queries become slow
- If need to search by media type
- If implementing media analytics
- If media reuse is needed

**Schema:**
```sql
CREATE TABLE media_files (
    id INTEGER PRIMARY KEY,
    tweet_id INTEGER REFERENCES tweets(id) ON DELETE CASCADE,
    thread_position INTEGER,  -- 1-based position in thread
    media_type VARCHAR(20),   -- 'photo' or 'video'
    source_url VARCHAR(1024),
    local_path VARCHAR(512),
    file_size INTEGER,
    download_status VARCHAR(20),
    created_at TIMESTAMP,

    INDEX ix_media_tweet (tweet_id),
    INDEX ix_media_type (media_type),
    INDEX ix_media_status (download_status)
);
```

**Migration:**
```python
def migrate_media_paths_to_table(db):
    """Migrate existing media_paths JSON to MediaFile table."""
    tweets_with_media = db.query(Tweet).filter(
        Tweet.media_paths.isnot(None)
    ).all()

    for tweet in tweets_with_media:
        try:
            media_list = json.loads(tweet.media_paths)

            for idx, media_item in enumerate(media_list, 1):
                db.add(MediaFile(
                    tweet_id=tweet.id,
                    thread_position=idx,
                    media_type=media_item['type'],
                    source_url=media_item['src'],
                    local_path=media_item.get('local_path'),
                    download_status='success' if media_item.get('local_path') else 'pending'
                ))
        except json.JSONDecodeError:
            logger.warning(f"Invalid media_paths for tweet {tweet.id}")

    db.commit()
```

---

### Phase 4: Advanced Features (Future) 🚀

#### 4.1 Media Gallery View

- Grid layout for all thread media
- Lightbox for full-size viewing
- Download buttons for individual files
- Drag-and-drop reordering

#### 4.2 Auto-scrape on URL Paste

```python
# In app.py
url = st.text_input(
    "Thread URL",
    placeholder="https://x.com/user/status/1234567890",
    key="scrape_url",
    on_change=handle_url_change  # Trigger on paste
)

def handle_url_change():
    url = st.session_state.scrape_url
    if url and url.startswith('https://x.com') and '/status/' in url:
        # Debounce: only scrape if URL hasn't changed for 1 second
        time.sleep(1)
        if url == st.session_state.scrape_url:
            # Trigger scrape
            st.session_state.auto_scrape_url = url
```

#### 4.3 Media Processing

- Thumbnail generation
- Video frame extraction
- Compression for large files
- Alt text generation (AI)

#### 4.4 Thread Analytics

- Average engagement per thread
- Best performing thread structures
- Media type performance
- Optimal thread length

---

## Implementation Priority

### ✅ Week 1: Core Translation (Phase 1.1) - COMPLETED
- [x] Add `translate_thread_consolidated()` method ✅
- [x] Add `translate_thread_separate()` method ✅
- [x] Hook up in dashboard scraping flow ✅
- [ ] Test with 3+ tweet threads ⏳ (IN PROGRESS)
- [ ] Compare old vs new translation quality ⏳ (IN PROGRESS)

**Success Criteria:**
- Consolidated threads translate as ONE flowing post
- No "1/5, 2/5" markers in output
- Natural Hebrew paragraph structure
- Translation quality improved (subjective but measurable)

**Files Modified:**
- `src/processor/processor.py` - Added 2 new translation methods (200+ lines)
- `src/dashboard/app.py` - Integrated auto-translate with context awareness
  - New "Auto-translate" checkbox
  - Consolidated mode uses `translate_thread_consolidated()`
  - Separate mode uses `translate_thread_separate()`
  - Smart status management (PROCESSED vs PENDING)

**Commit Status:** Ready to commit (pending testing)

### ✅ Week 2: Media Download (Phase 1.2) - COMPLETED
- [x] Add `media_paths` column to database ✅
- [x] Write migration script ✅
- [x] Integrate `download_thread_media()` in dashboard ✅
- [x] Test with various media types ✅
- [x] Handle download failures gracefully ✅

**Success Criteria:**
- All thread media downloaded and stored
- JSON correctly stores all media paths
- Files exist in `data/media/` directory
- Download errors logged but don't block processing

**Files Modified:**
- `src/common/models.py` - Added `media_paths` column + migration
- `src/dashboard/app.py` - Hooked up `download_thread_media()` in scraping
- `tests/test_thread_media.py` - Added 9 new tests

### ✅ Week 3: Media UI (Phase 1.3) - COMPLETED
- [x] Add media indicators to queue list ✅
- [x] Build media gallery in editor ✅
- [x] Show thumbnails for images ✅
- [x] Display video icons for videos ✅
- [x] Handle missing files gracefully ✅

**Success Criteria:**
- Media count visible in queue
- Thumbnails display correctly
- Missing media shows error icon
- Gallery works with 10+ images

**Files Modified:**
- `src/dashboard/app.py` - `render_content_item()` with media indicators
- `src/dashboard/app.py` - `render_editor()` with media gallery section

### Week 4: Preview & Edit (Phase 2.1)
- [ ] Build thread preview UI
- [ ] Add tweet selection checkboxes
- [ ] Implement reorder buttons
- [ ] Process selected tweets to queue
- [ ] Add cancel functionality

**Success Criteria:**
- Preview shows after scraping
- Can remove tweets before processing
- Reordering works correctly
- Selected tweets processed correctly

---

## Testing Strategy

### Manual Testing Checklist

**Test Cases:**

1. **Simple Thread (2-3 tweets, no media)**
   - Scrape thread
   - Verify consolidation works
   - Check translation quality
   - Verify separate mode works

2. **Media-Heavy Thread (5+ tweets, 10+ images)**
   - Scrape thread
   - Verify all media downloads
   - Check JSON storage
   - View in editor gallery

3. **Video Thread (2+ videos)**
   - Scrape thread with videos
   - Verify yt-dlp downloads work
   - Check video files exist
   - Test video playback in UI

4. **Long Thread (10+ tweets)**
   - Scrape long thread
   - Verify performance acceptable
   - Check memory usage
   - Test preview UI with many items

5. **Error Cases**
   - Invalid URL
   - Private/deleted tweet
   - Network failure during download
   - Disk full scenario

### Automated Testing

**Unit Tests:**
```python
# tests/test_thread_translation.py
def test_translate_thread_consolidated():
    translator = TranslationService(config)
    tweets = [
        {"text": "First tweet about fintech"},
        {"text": "Second tweet with more details"},
        {"text": "Final thoughts and conclusion"}
    ]

    result = translator.translate_thread_consolidated(tweets)

    assert len(result) > 0
    assert "---" not in result  # No separators
    assert is_hebrew(result)  # Helper function to check Hebrew

def test_translate_thread_separate():
    translator = TranslationService(config)
    tweets = [
        {"text": "Tweet 1"},
        {"text": "Tweet 2"},
    ]

    results = translator.translate_thread_separate(tweets)

    assert len(results) == 2
    assert all(is_hebrew(r) for r in results)
```

**Integration Tests:**
```python
# tests/test_thread_media_download.py
@pytest.mark.integration
def test_download_thread_media():
    downloader = MediaDownloader()

    thread_data = {
        'tweets': [
            {
                'tweet_id': '123',
                'media': [
                    {'type': 'photo', 'src': 'https://pbs.twimg.com/media/test.jpg'}
                ]
            }
        ]
    }

    results = downloader.download_thread_media(thread_data)

    assert len(results) == 1
    assert results[0]['local_path'] is not None
    assert Path(results[0]['local_path']).exists()
```

---

## Known Issues & Limitations

### Current Limitations

1. **Single Media URL Field**
   - Database stores only one `media_url`
   - Threads with multiple media lose files
   - **Fix:** Add `media_paths` JSON column (Phase 1.2)

2. **No Thread Context in Translation**
   - Each tweet translated independently
   - Loses narrative flow
   - **Fix:** Implement context-aware translation (Phase 1.1)

3. **No Media Download**
   - `download_thread_media()` never called
   - Media lost after scraping
   - **Fix:** Hook up in dashboard (Phase 1.2)

4. **No Preview/Edit**
   - Can't modify thread before processing
   - All-or-nothing approach
   - **Fix:** Build preview UI (Phase 2.1)

### Future Considerations

1. **Translation Cost**
   - GPT-4o API costs add up for long threads
   - Consider caching translations
   - Maybe add cheaper model option for drafts

2. **Media Storage**
   - Videos can be large (>100MB)
   - Need storage limits and cleanup
   - Consider compression or external storage

3. **Rate Limiting**
   - OpenAI rate limits on translation
   - X rate limits on scraping
   - Need exponential backoff and retries

4. **Concurrent Processing**
   - Current: one thread at a time
   - Future: parallel processing for batch jobs
   - Need queue system (Celery, Redis)

---

## Success Metrics

### Translation Quality
- [ ] 90%+ of consolidated threads translate as flowing narrative
- [ ] No "1/5" markers in consolidated output
- [ ] User satisfaction rating ≥4/5

### Media Handling
- [ ] 100% of thread media downloaded (when accessible)
- [ ] All media visible in UI
- [ ] Zero data loss from current state

### User Experience
- [ ] Thread preview shown within 3 seconds of scraping
- [ ] Media gallery loads in <2 seconds
- [ ] Can edit thread structure in <30 seconds

### Performance
- [ ] 5-tweet thread processes in <20 seconds
- [ ] 10+ media files download in <60 seconds
- [ ] UI remains responsive during processing

---

## Rollout Plan

### Phase 1 (Weeks 1-3): Foundation
1. Deploy context-aware translation
2. Deploy media download pipeline
3. Deploy media visibility UI
4. **User Testing:** Get feedback on translation quality
5. **Iteration:** Adjust prompts based on feedback

### Phase 2 (Week 4): UX Polish
1. Deploy preview & edit UI
2. **User Testing:** Test with real workflows
3. **Iteration:** Fix usability issues

### Phase 3 (Future): Advanced Features
1. Evaluate need for MediaFile table
2. Consider auto-scrape feature
3. Build analytics if needed

### Rollback Plan
- Keep old code commented out for 1 week
- Database changes are additive (no data loss)
- Can disable new features via feature flags

---

## Open Questions

1. **Media Storage Strategy:**
   - Q: Should we store media in database (as MediaFile table) or keep as JSON in Tweet?
   - A: Start with JSON (simpler), migrate to table if needed for querying/analytics

2. **Translation Cache:**
   - Q: Should we cache translations to reduce API costs?
   - A: Not initially. Add if costs become significant (>$50/month)

3. **Narrative vs Concatenated:**
   - Q: Should we make narrative mode the default?
   - A: Yes, based on user preference for "flowing narrative"

4. **Media Preview:**
   - Q: Should we show media preview during scraping (before download)?
   - A: No, keep scraping fast. Show in preview/editor after download

5. **Error Handling:**
   - Q: What if one tweet's media fails to download?
   - A: Continue processing, log error, show warning in UI. Don't block entire thread.

---

## Resources Needed

### Development
- 4 weeks developer time (1 developer)
- Access to OpenAI API (GPT-4o)
- X account for scraping tests

### Testing
- Test account with sample threads
- Variety of thread types (text-only, media-heavy, long)
- Test videos and images

### Infrastructure
- Storage for media files (assume 10GB initially)
- Database backup before schema changes
- Monitoring for API costs

---

## Appendix: Code Snippets

### A. Enhanced Translation Prompt

```python
CONSOLIDATED_THREAD_PROMPT = """You are translating a Twitter THREAD into Hebrew.

CRITICAL INSTRUCTIONS:
1. This is a THREAD (multiple tweets by same author)
2. Rewrite as ONE FLOWING HEBREW POST
3. NO thread markers (1/5, 2/5, etc.)
4. NO separators (---, ===, etc.)
5. Combine into SINGLE narrative
6. Use natural Hebrew paragraphs
7. Preserve ALL key information
8. Max 280 chars if possible, otherwise natural break points

Thread contains {tweet_count} tweets. Create ONE unified Hebrew post.

Original thread:
{thread_text}

Output ONLY the Hebrew translation."""
```

### B. Media Path Storage Format

```json
[
  {
    "tweet_id": "1234567890",
    "tweet_number": 1,
    "type": "photo",
    "src": "https://pbs.twimg.com/media/abc123.jpg",
    "local_path": "/data/media/images/image_20260128_123456_abc123.jpg",
    "download_status": "success"
  },
  {
    "tweet_id": "1234567891",
    "tweet_number": 2,
    "type": "video",
    "src": "https://video.twimg.com/amplify_video/xyz789/pl/playlist.m3u8",
    "local_path": "/data/media/videos/video_20260128_123457_xyz789.mp4",
    "download_status": "success"
  }
]
```

### C. Thread Preview State Schema

```python
st.session_state.thread_preview = {
    'url': 'https://x.com/user/status/123',
    'data': {
        'source_url': 'https://x.com/user/status/123',
        'author_handle': '@elonmusk',
        'author_name': 'Elon Musk',
        'tweet_count': 5,
        'tweets': [ ... ],
        'scraped_at': '2026-01-28T10:30:00Z'
    },
    'tweets': [
        {
            'tweet_id': '123',
            'author_handle': '@elonmusk',
            'author_name': 'Elon Musk',
            'text': 'First tweet...',
            'permalink': 'https://x.com/elonmusk/status/123',
            'timestamp': '2026-01-28T10:00:00Z',
            'media': [
                {'type': 'photo', 'src': 'https://...', 'alt': ''}
            ]
        },
        # ... more tweets
    ],
    'selected': [0, 1, 2, 4],  # Indices of selected tweets
    'consolidate': True,
    'auto_translate': True
}
```

---

---

## 🔧 Quick Reference - Phase 1.1 Implementation

### How to Test

1. **Restart Streamlit:**
   ```bash
   pkill -f streamlit
   cd src/dashboard
   python3 -m streamlit run app.py
   ```

2. **Navigate to:** Content → Acquire tab

3. **Scrape a thread:**
   - Paste thread URL
   - ✅ Check "Add to queue"
   - ✅ Check "Consolidate thread" (for flowing narrative)
   - ✅ Check "Auto-translate"
   - Click "Scrape Thread"

4. **View Results:**
   - Go to Content → Queue tab
   - Find thread (status = PROCESSED)
   - Click "Edit" to see Hebrew translation

### Key Features

**Consolidated Mode:**
```
Input: 3-tweet thread
Output: ONE flowing Hebrew post
Features:
  - No "1/5" markers
  - No "---" separators
  - Natural paragraphs
  - Full context awareness
```

**Separate Mode:**
```
Input: 3-tweet thread
Output: 3 Hebrew tweets
Features:
  - Each tweet aware of previous tweets
  - No repetition
  - Context continuity
  - Maintains thread structure
```

### Code Locations

**Translation Methods:**
- File: `src/processor/processor.py`
- Lines: ~336-590
- Methods:
  - `translate_thread_consolidated(tweets: List[Dict]) -> str`
  - `translate_thread_separate(tweets: List[Dict]) -> List[str]`

**Dashboard Integration:**
- File: `src/dashboard/app.py`
- Lines: ~1002-1090
- Features:
  - Auto-translate checkbox
  - Consolidated translation integration
  - Separate translation integration
  - Progress indicators

### System Prompts

**Consolidated Mode Key Instructions:**
```
- This is {len(tweets)} tweets forming ONE story
- Rewrite as SINGLE FLOWING HEBREW POST
- NO thread markers (1/5, 2/5)
- NO separators (---, ===)
- Combine into ONE cohesive narrative
```

**Separate Mode Key Instructions:**
```
- Tweet {idx+1}/{len(tweets)} from a thread
- Consider context from previous tweets
- Avoid repeating information
- Maintain narrative continuity
```

### Troubleshooting

**Issue:** "OpenAI API Error"
- **Check:** `.env` has `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-4o`, `OPENAI_TEMPERATURE=0.7`
- **Fix:** Set environment variables, restart Streamlit

**Issue:** Translation still has "1/5" markers
- **Likely Cause:** GPT not following prompt
- **Fix:** Try different thread, check prompt in logs
- **Future:** May need prompt adjustment

**Issue:** "Translation failed" warning
- **Result:** Thread added as PENDING (no translation)
- **Fix:** Can translate manually later with "Translate" button
- **Check:** Logs for specific error

**Issue:** Hebrew output is poor quality
- **Fix:** Adjust system prompt, increase temperature, or use different model
- **Report:** Document in Testing Results section above

### Success Metrics

✅ **Translation completes without errors**
✅ **Consolidated output is ONE post (no separators)**
✅ **No thread markers (1/5, etc.) in output**
✅ **Hebrew quality is natural and flowing**
✅ **Context awareness reduces repetition**
✅ **User feedback is clear and helpful**

---

**End of Thread Scraping Improvement Plan**

**Next Steps:**
1. ✅ ~~Phase 1.1 Implementation~~ (COMPLETE)
2. 🧪 Test Phase 1.1 (fill in Testing Results section)
3. 📊 Review results and assess quality
4. 🚀 Proceed to Phase 1.2 (Media Download) or iterate on 1.1

**Questions? Issues?** Document in Testing Results section or create GitHub issue.

**Git Commit Checklist:**
- [ ] Tested consolidated translation
- [ ] Tested separate translation
- [ ] Verified no thread markers in output
- [ ] Checked quality acceptable
- [ ] Updated CLAUDE.md with new features
- [ ] Ready to commit: `git add -A && git commit -m "feat: context-aware thread translation (Phase 1.1)"`
