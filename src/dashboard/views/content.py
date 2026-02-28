import streamlit as st
import html
import json
import time
import asyncio
import logging
from datetime import datetime, timezone
from common.models import Tweet, Trend, Thread, TrendSource, TweetStatus, StyleExample
from dashboard.db_helpers import get_stats, get_tweets, update_tweet, delete_tweet
from dashboard.helpers import get_source_badge_class, parse_media_info, format_status_str
from dashboard.lazy_loaders import get_style_manager, get_summary_generator, get_auto_pipeline
from dashboard.state import (
    KEY_CONTENT_SECTION_SELECTOR,
    get_content_tab,
    get_selected_item,
    push_flash,
    set_content_tab,
    set_current_view,
    set_selected_item,
    rerun_view,
)
from dashboard.ui_components import render_empty_state, render_page_header, render_section_header
from dashboard.ux_events import log_ux_event
from dashboard.validators import validate_x_url, validate_safe_url

# Cooldown constants (seconds)
_SCRAPE_COOLDOWN = 30
_FETCH_ALL_COOLDOWN = 60

logger = logging.getLogger(__name__)


def render_content(db):
    """Content view - acquire content and manage queue"""

    render_page_header("Content", "Acquire, review, generate, and hand off content for publishing.")

    # Auto-translate if triggered
    if st.session_state.get('auto_translate'):
        st.session_state.auto_translate = False
        run_batch_translate(db)

    # If editing a specific item, show editor
    selected_item = get_selected_item()
    if selected_item:
        render_editor(db, selected_item)
        return

    sections = ["Acquire", "Queue", "Thread Translation", "Generate", "Publish"]
    current_section = get_content_tab()
    if current_section not in sections:
        current_section = "Acquire"

    # Keep the widget key synchronized with external navigation requests
    # (e.g., Home -> Content -> Generate) before the widget is instantiated.
    if st.session_state.get(KEY_CONTENT_SECTION_SELECTOR) != current_section:
        st.session_state[KEY_CONTENT_SECTION_SELECTOR] = current_section

    section = st.radio(
        "Content section",
        sections,
        key=KEY_CONTENT_SECTION_SELECTOR,
        horizontal=True,
    )
    if section != current_section:
        set_content_tab(section)

    if section == "Acquire":
        _render_acquire_section(db)
    elif section == "Queue":
        _render_queue_section(db)
    elif section == "Thread Translation":
        _render_thread_translation(db)
    elif section == "Generate":
        _render_generate_section(db)
    else:
        render_publish_handoff(db)


def _render_acquire_section(db):
    """Acquire section: thread scraper + trend fetching"""

    # ---- Thread Scraper ----
    render_section_header("Scrape Thread from X", "Fetch a thread, optionally translate, and add to queue.")

    remaining = int(_SCRAPE_COOLDOWN - (time.time() - st.session_state.get("last_scrape_time", 0)))
    if remaining > 0:
        st.caption(f"Scrape cooldown active: {remaining}s remaining.")

    with st.form("scrape_thread_form"):
        url = st.text_input(
            "Thread URL",
            placeholder="https://x.com/user/status/1234567890",
            key="scrape_url",
            max_chars=500,
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            add_to_queue = st.checkbox("Add to queue", value=True)
        with col2:
            consolidate = st.checkbox("Consolidate thread", value=True)
        with col3:
            auto_translate = st.checkbox("Auto-translate", value=True, help="Translate using context-aware AI")
        with col4:
            download_media = st.checkbox("Download media", value=False, help="Download images and videos from thread")

        scrape_clicked = st.form_submit_button("Scrape Thread", type="primary", use_container_width=True)

    if scrape_clicked:
        _url_valid, _url_err = validate_x_url(url) if url else (False, "")
        if not url:
            st.warning("Enter a URL before scraping.")
        elif not _url_valid:
            st.error(_url_err)
        elif time.time() - st.session_state.get("last_scrape_time", 0) < _SCRAPE_COOLDOWN:
            remaining = int(_SCRAPE_COOLDOWN - (time.time() - st.session_state.get("last_scrape_time", 0)))
            st.warning(f"Please wait {remaining}s before scraping again.")
        else:
            st.session_state.last_scrape_time = time.time()
            with st.spinner("Scraping..."):
                try:
                    from scraper.scraper import TwitterScraper

                    progress = st.progress(0, "Connecting...")

                    async def run():
                        scraper = TwitterScraper()
                        try:
                            progress.progress(20, "Logging in...")
                            await scraper.ensure_logged_in()
                            progress.progress(40, "Fetching thread...")
                            return await scraper.fetch_raw_thread(url, author_only=True)
                        finally:
                            await scraper.close()

                    result = asyncio.run(run())
                    tweets_data = result.get("tweets", [])
                    progress.progress(80, "Saving...")

                    if add_to_queue:
                        if consolidate and len(tweets_data) > 1:
                            combined_text = "\n\n---\n\n".join([t.get("text", "") for t in tweets_data])
                            first_url = tweets_data[0].get("permalink", url) if tweets_data else url
                            media_urls = [t["media"][0]["src"] for t in tweets_data if t.get("media")]

                            if not db.query(Tweet).filter_by(source_url=first_url).first():
                                hebrew_draft = None
                                tweet_status = TweetStatus.PENDING

                                if auto_translate:
                                    progress.progress(60, "Translating with context awareness...")
                                    try:
                                        from processor.processor import ProcessorConfig, TranslationService
                                        config = ProcessorConfig()
                                        translator = TranslationService(config)
                                        hebrew_draft = translator.translate_thread_consolidated(tweets_data)
                                        tweet_status = TweetStatus.PROCESSED
                                        logger.info("Context-aware consolidated translation complete")
                                    except Exception as e:
                                        logger.error(f"Translation failed: {e}")
                                        st.warning(f"Translation failed: {str(e)[:80]}. Added without translation.")

                                media_paths_json = None
                                first_media_path = None
                                if download_media:
                                    try:
                                        progress.progress(75, "Downloading media...")
                                        from processor.processor import MediaDownloader
                                        downloader = MediaDownloader()
                                        media_results = downloader.download_thread_media(result)
                                        if media_results:
                                            import json as json_mod
                                            media_paths_json = json_mod.dumps(media_results)
                                            first_media_path = media_results[0].get("local_path")
                                            logger.info(f"Downloaded {len(media_results)} media files")
                                    except Exception as e:
                                        logger.warning(f"Media download failed: {e}")

                                db.add(
                                    Tweet(
                                        source_url=first_url,
                                        original_text=combined_text,
                                        hebrew_draft=hebrew_draft,
                                        status=tweet_status,
                                        media_url=media_urls[0] if media_urls else None,
                                        media_path=first_media_path,
                                        media_paths=media_paths_json,
                                        trend_topic=result.get("author_handle", ""),
                                    )
                                )
                                db.commit()
                                progress.progress(100, "Done!")
                                if auto_translate and hebrew_draft:
                                    push_flash(
                                        "success",
                                        f"Added and translated consolidated thread ({len(tweets_data)} tweets to 1 post).",
                                        view="content",
                                    )
                                else:
                                    push_flash("success", f"Added consolidated thread ({len(tweets_data)} tweets).", view="content")
                            else:
                                progress.progress(100, "Done!")
                                push_flash("info", "Thread already exists in queue.", view="content")
                        else:
                            saved = 0
                            hebrew_translations = []
                            if auto_translate and tweets_data:
                                progress.progress(60, "Translating with context awareness...")
                                try:
                                    from processor.processor import ProcessorConfig, TranslationService
                                    config = ProcessorConfig()
                                    translator = TranslationService(config)
                                    hebrew_translations = translator.translate_thread_separate(tweets_data)
                                    logger.info("Context-aware separate translation complete")
                                except Exception as e:
                                    logger.error(f"Translation failed: {e}")
                                    st.warning(f"Translation failed: {str(e)[:80]}. Added without translation.")

                            for idx, t in enumerate(tweets_data):
                                permalink = t.get("permalink", "")
                                if permalink and not db.query(Tweet).filter_by(source_url=permalink).first():
                                    media_url = t["media"][0]["src"] if t.get("media") else None
                                    hebrew_draft = None
                                    tweet_status = TweetStatus.PENDING
                                    if hebrew_translations and idx < len(hebrew_translations):
                                        hebrew_draft = hebrew_translations[idx]
                                        tweet_status = TweetStatus.PROCESSED

                                    db.add(
                                        Tweet(
                                            source_url=permalink,
                                            original_text=t.get("text", ""),
                                            hebrew_draft=hebrew_draft,
                                            status=tweet_status,
                                            media_url=media_url,
                                            trend_topic=t.get("author_handle", ""),
                                        )
                                    )
                                    saved += 1

                            db.commit()
                            progress.progress(100, "Done!")
                            if auto_translate and hebrew_translations:
                                push_flash("success", f"Added and translated {saved} tweets.", view="content")
                            else:
                                push_flash("success", f"Added {saved} tweets to queue.", view="content")
                    else:
                        existing = db.query(Thread).filter_by(source_url=url).first()
                        if existing:
                            existing.raw_json = json.dumps(tweets_data)
                            existing.tweet_count = len(tweets_data)
                            existing.updated_at = datetime.now(timezone.utc)
                        else:
                            thread = Thread(
                                source_url=url,
                                author_handle=result.get("author_handle", ""),
                                author_name=result.get("author_name", ""),
                                raw_json=json.dumps(tweets_data),
                                tweet_count=len(tweets_data),
                                status=TweetStatus.PENDING,
                            )
                            db.add(thread)
                        db.commit()
                        progress.progress(100, "Done!")
                        push_flash("success", f"Saved thread with {len(tweets_data)} tweets.", view="content")

                    log_ux_event("scrape_thread", "content", success=True, metadata={"tweets_found": len(tweets_data)})
                    rerun_view()
                except Exception as e:
                    logger.error(f"Scrape failed: {e}")
                    log_ux_event("scrape_thread", "content", success=False, error_code="scrape_failed")
                    st.error("Scrape failed. Check server logs for details.")

    st.markdown("---")

    # ---- Autopilot Pipeline ----
    st.markdown("### Autopilot Pipeline")
    st.markdown('<p style="color: var(--text-secondary); font-size: 0.85rem;">Two-phase workflow: discover trends, confirm relevance, then generate Hebrew posts.</p>', unsafe_allow_html=True)

    # Initialize pipeline session state
    if 'pipeline_phase' not in st.session_state:
        st.session_state.pipeline_phase = 'idle'
    if 'pipeline_candidates' not in st.session_state:
        st.session_state.pipeline_candidates = []
    if 'pipeline_results' not in st.session_state:
        st.session_state.pipeline_results = []

    # Read autopilot defaults from session state
    ap_top_n = st.session_state.get('autopilot_top_n', 3)
    ap_angle = st.session_state.get('autopilot_angle', 'news')
    ap_auto_summarize = st.session_state.get('autopilot_auto_summarize', True)

    # ---- Phase A: Fetch & Analyze ----
    if st.session_state.pipeline_phase == 'idle':
        if st.button("Fetch & Analyze", type="primary", use_container_width=False, key="pipeline_fetch"):
            pipeline = get_auto_pipeline()
            if not pipeline:
                st.error("Could not initialize pipeline. Check OPENAI_API_KEY.")
            else:
                with st.spinner("Fetching & ranking articles..."):
                    try:
                        candidates = pipeline.fetch_and_rank(
                            db, top_n=ap_top_n,
                            auto_summarize=ap_auto_summarize,
                        )
                        if candidates:
                            st.session_state.pipeline_candidates = candidates
                            st.session_state.pipeline_phase = 'candidates'
                            rerun_view()
                        else:
                            st.info("No new candidates found. All top trends are already in your queue.")
                    except Exception as e:
                        logger.error(f"Pipeline failed: {e}")
                        st.error("Pipeline failed. Check server logs for details.")

    # ---- Phase A UI: Candidate selection ----
    elif st.session_state.pipeline_phase == 'candidates':
        candidates = st.session_state.pipeline_candidates
        st.markdown(f"#### Select Trends to Generate ({len(candidates)} candidates)")

        selections = {}
        for idx, cand in enumerate(candidates):
            safe_title = html.escape(cand.get('title', ''))
            safe_summary = html.escape(cand.get('summary', '') or cand.get('description', ''))[:200]
            badge_cls = get_source_badge_class(cand.get('source', ''))
            safe_source = html.escape(cand.get('source', ''))
            category_label = "Finance" if cand.get("category") == "Finance" else "Tech"
            url = cand.get('url', '')
            url_valid = bool(url) and validate_safe_url(url)[0]

            with st.container():
                sel_col, info_col = st.columns([0.3, 5])
                with sel_col:
                    checked = st.checkbox(f"Select candidate {idx + 1}", value=True, key=f"pipe_sel_{idx}")
                    selections[idx] = checked
                with info_col:
                    title_html = (
                        f'<a href="{html.escape(url)}" target="_blank" style="color: var(--accent-primary); text-decoration: none; font-weight: 500;">{safe_title}</a>'
                        if url_valid else f'<span style="font-weight: 500;">{safe_title}</span>'
                    )
                    st.markdown(f"""
                        <div style="padding: 0.5rem 0;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <span style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted);">#{idx+1}</span>
                                <span class="status-badge {'category-finance' if category_label == 'Finance' else 'category-tech'}">{category_label}</span>
                                {title_html}
                                <span class="status-badge {badge_cls}" style="font-size: 0.65rem;">{safe_source}</span>
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.3rem; line-height: 1.4;">{safe_summary}</div>
                        </div>
                    """, unsafe_allow_html=True)
                st.markdown("<hr style='margin: 0.25rem 0; border-color: var(--border-default);'>", unsafe_allow_html=True)

        gen_col1, gen_col2, gen_col3 = st.columns([2, 1, 1])
        with gen_col1:
            selected_count = sum(1 for v in selections.values() if v)
            st.markdown(f"**{selected_count}** trend{'s' if selected_count != 1 else ''} selected")
        with gen_col2:
            if st.button("Generate Hebrew", type="primary", use_container_width=True, key="pipeline_generate", disabled=selected_count == 0):
                confirmed_ids = [candidates[i]['trend_id'] for i, sel in selections.items() if sel]
                pipeline = get_auto_pipeline()
                if pipeline:
                    with st.spinner(f"Generating Hebrew posts for {len(confirmed_ids)} trends..."):
                        try:
                            results = pipeline.generate_for_confirmed(
                                db, confirmed_ids, angle=ap_angle, num_variants=1,
                            )
                            st.session_state.pipeline_results = results
                            st.session_state.pipeline_phase = 'review'
                            rerun_view()
                        except Exception as e:
                            logger.error(f"Generation failed: {e}")
                            st.error("Generation failed. Check server logs for details.")
        with gen_col3:
            if st.button("Cancel", use_container_width=True, key="pipeline_cancel_a"):
                st.session_state.pipeline_phase = 'idle'
                st.session_state.pipeline_candidates = []
                rerun_view()

    # ---- Phase B UI: Review generated posts ----
    elif st.session_state.pipeline_phase == 'review':
        results = st.session_state.pipeline_results
        st.markdown(f"#### Review Generated Posts ({len(results)})")

        for idx, res in enumerate(results):
            safe_title = html.escape(res.get('trend_title', ''))
            variants = res.get('variants', [])
            best = variants[0] if variants else {}
            hebrew_text = best.get('content', '')
            tweet_id = res.get('tweet_id')

            st.markdown(f"**{safe_title}**")

            edited = st.text_area(
                f"Hebrew post {idx+1}",
                value=hebrew_text,
                height=120,
                key=f"pipe_review_{idx}",
            )

            char_count = len(edited) if edited else 0
            over = char_count > 280
            st.markdown(
                f"<div style='text-align:right; font-size:0.75rem; color: {'var(--accent-danger)' if over else 'var(--text-muted)'};'>"
                f"{char_count}/280</div>",
                unsafe_allow_html=True,
            )

            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("Approve", key=f"pipe_approve_{idx}", use_container_width=True, type="primary"):
                    if tweet_id:
                        tweet = db.query(Tweet).filter_by(id=tweet_id).first()
                        if tweet:
                            tweet.hebrew_draft = edited
                            tweet.status = TweetStatus.APPROVED
                            db.commit()
                            if edited and len(edited.strip()) > 30:
                                _auto_learn_style(db, edited.strip())
                            st.success(f"Approved: {safe_title}")
                            rerun_view()
            with btn_col2:
                if st.button("Skip", key=f"pipe_skip_{idx}", use_container_width=True):
                    if tweet_id:
                        tweet = db.query(Tweet).filter_by(id=tweet_id).first()
                        if tweet:
                            # Record negative feedback for style learning
                            from processor.prompt_builder import extract_topic_keywords
                            skip_tags = extract_topic_keywords(res.get('trend_title', ''))
                            _record_style_feedback(db, skip_tags, approved=False)
                            db.delete(tweet)
                            db.commit()
                    st.info(f"Skipped: {safe_title}")
                    rerun_view()

            st.markdown("<hr style='margin: 0.5rem 0; border-color: var(--border-default);'>", unsafe_allow_html=True)

        done_col1, done_col2, done_col3 = st.columns(3)
        with done_col1:
            if st.button("Approve All", type="primary", use_container_width=True, key="pipe_approve_all"):
                for idx, res in enumerate(results):
                    tweet_id = res.get('tweet_id')
                    if tweet_id:
                        tweet = db.query(Tweet).filter_by(id=tweet_id).first()
                        if tweet and tweet.status != TweetStatus.APPROVED:
                            edited_key = f"pipe_review_{idx}"
                            edited_text = st.session_state.get(edited_key, tweet.hebrew_draft)
                            tweet.hebrew_draft = edited_text
                            tweet.status = TweetStatus.APPROVED
                            if edited_text and len(edited_text.strip()) > 30:
                                _auto_learn_style(db, edited_text.strip())
                db.commit()
                st.success(f"Approved all {len(results)} posts!")
                st.session_state.pipeline_phase = 'idle'
                st.session_state.pipeline_candidates = []
                st.session_state.pipeline_results = []
                rerun_view()
        with done_col2:
            if st.button("Back to Candidates", use_container_width=True, key="pipe_back"):
                st.session_state.pipeline_phase = 'candidates'
                st.session_state.pipeline_results = []
                rerun_view()
        with done_col3:
            if st.button("Done", use_container_width=True, key="pipe_done"):
                st.session_state.pipeline_phase = 'idle'
                st.session_state.pipeline_candidates = []
                st.session_state.pipeline_results = []
                rerun_view()

    st.markdown("---")

    # ---- Fetch All Trends (Manual) ----
    with st.expander("Manual Trend Fetching", expanded=False):
        fcol1, fcol2, fcol3 = st.columns([2, 1, 1])
        with fcol1:
            st.markdown('<p style="color: var(--text-secondary); font-size: 0.85rem;">Fetch articles with weighted sampling: 70% finance + 30% tech, ranked by keyword overlap.</p>', unsafe_allow_html=True)
        with fcol2:
            auto_summarize = st.checkbox("Auto-summarize", value=True, key="auto_gen_summary", help="Generate AI summaries automatically when fetching trends")
            st.session_state.auto_generate_summaries = auto_summarize
        with fcol3:
            fetch_all = st.button("Fetch All Trends", type="primary", use_container_width=True, key="fetch_all_trends")

        # Generate Summaries button for existing trends without summaries
        trends_without_summary = db.query(Trend).filter(Trend.summary == None).count()
        if trends_without_summary > 0:
            gcol1, gcol2 = st.columns([3, 1])
            with gcol1:
                st.markdown(f'<p style="color: var(--text-muted); font-size: 0.8rem;">{trends_without_summary} trends need AI summaries</p>', unsafe_allow_html=True)
            with gcol2:
                if st.button("Generate Summaries", key="gen_summaries_btn", use_container_width=True):
                    generator = get_summary_generator()
                    if generator:
                        with st.spinner(f"Generating summaries for {trends_without_summary} trends..."):
                            stats = generator.backfill_summaries(db, limit=20)
                            st.success(f"Generated {stats['success']} summaries ({stats['failed']} failed)")
                            rerun_view()
                    else:
                        st.error("Could not initialize summary generator. Check OPENAI_API_KEY.")

        if fetch_all and time.time() - st.session_state.get('last_fetch_all_time', 0) < _FETCH_ALL_COOLDOWN:
            remaining = int(_FETCH_ALL_COOLDOWN - (time.time() - st.session_state.get('last_fetch_all_time', 0)))
            st.warning(f"Please wait {remaining}s before fetching again.")
        elif fetch_all:
            st.session_state.last_fetch_all_time = time.time()
            with st.spinner("Fetching from all sources..."):
                try:
                    from scraper.news_scraper import NewsScraper
                    scraper = NewsScraper()
                    ranked_news = scraper.get_latest_news(limit_per_source=10, total_limit=10, finance_weight=0.7)

                    source_map = {
                        'Yahoo Finance': TrendSource.YAHOO_FINANCE,
                        'WSJ': TrendSource.WSJ,
                        'TechCrunch': TrendSource.TECHCRUNCH,
                        'Bloomberg': TrendSource.BLOOMBERG,
                        'MarketWatch': TrendSource.MARKETWATCH,
                    }
                    saved = 0
                    new_trend_ids = []
                    _existing_titles = {t.title for t in db.query(Trend.title).filter(Trend.title.in_([a['title'] for a in ranked_news])).all()}
                    for article in ranked_news:
                        if article['title'] not in _existing_titles:
                            new_trend = Trend(
                                title=article['title'],
                                description=article.get('description', '')[:500],
                                source=source_map.get(article['source'], TrendSource.MANUAL),
                                article_url=article.get('url', ''),
                            )
                            db.add(new_trend)
                            db.flush()
                            new_trend_ids.append(new_trend.id)
                            saved += 1
                    db.commit()

                    st.session_state.ranked_articles = ranked_news
                    st.session_state.new_trend_ids = new_trend_ids
                    st.success(f"Fetched & ranked top {len(ranked_news)} articles, saved {saved} new trends")

                    if new_trend_ids and st.session_state.get('auto_generate_summaries', True):
                        generator = get_summary_generator()
                        if generator:
                            with st.spinner(f"Generating AI summaries for {len(new_trend_ids)} trends..."):
                                success_count = 0
                                for trend_id in new_trend_ids:
                                    if generator.process_trend(db, trend_id):
                                        success_count += 1
                                st.success(f"Generated {success_count} AI summaries")

                    set_current_view("home")
                    rerun_view()
                except Exception as e:
                    logger.error(f"Fetch trends failed: {e}")
                    st.error("Fetch failed. Check server logs for details.")

    # ---- Show Ranked Articles ----
    ranked = st.session_state.get('ranked_articles', None)
    if ranked:
        # Count distribution
        finance_count = sum(1 for a in ranked if a.get('category') == 'Finance')
        tech_count = sum(1 for a in ranked if a.get('category') == 'Tech')

        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0;">Top Articles (Ranked)</h3>
                <div style="display: flex; gap: 0.5rem;">
                    <span class="status-badge category-finance">Finance: {finance_count}</span>
                    <span class="status-badge category-tech">Tech: {tech_count}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Pre-fetch all matching trends to avoid N+1 queries
        _ranked_titles = [a.get('title', '') for a in ranked]
        _trend_by_title = {t.title: t for t in db.query(Trend).filter(Trend.title.in_(_ranked_titles)).all()} if _ranked_titles else {}

        for idx, art in enumerate(ranked, 1):
            raw_art_url = art.get('url', '') or ''
            art_url = html.escape(raw_art_url)
            art_title = html.escape(art.get('title', '') or '')
            art_desc = html.escape((art.get('description', '') or '')[:120])
            art_source = html.escape(art.get('source', '') or '')
            art_category = art.get('category', 'Unknown')
            badge_cls = get_source_badge_class(art.get('source', ''))
            category_label = "Finance" if art_category == "Finance" else "Tech"
            title_html = (
                f'<a href="{art_url}" target="_blank" style="color: var(--accent-primary); text-decoration: none; font-size: 0.9rem; font-weight: 500;">{art_title}</a>'
                if raw_art_url and validate_safe_url(raw_art_url)[0]
                else f'<span style="color: var(--text-primary); font-size: 0.9rem; font-weight: 500;">{art_title}</span>'
            )

            # Check if this trend has a summary in DB (pre-fetched)
            db_trend = _trend_by_title.get(art.get('title', ''))
            if db_trend and db_trend.summary:
                safe_summary = html.escape(db_trend.summary[:180])
                summary_html = f'<div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.35rem; line-height: 1.4; background: rgba(25, 154, 245, 0.05); padding: 0.5rem; border-radius: 6px; border-left: 2px solid var(--accent-primary);">{safe_summary}{"..." if len(db_trend.summary) > 180 else ""}</div>'
                # Show keywords
                keywords_html = ''
                if db_trend.keywords and isinstance(db_trend.keywords, list) and len(db_trend.keywords) > 0:
                    keywords_tags = ' '.join([f'<span style="background: var(--bg-tertiary); color: var(--text-muted); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.65rem; margin-right: 0.25rem;">{html.escape(str(kw))}</span>' for kw in db_trend.keywords[:4]])
                    keywords_html = f'<div style="margin-top: 0.35rem;">{keywords_tags}</div>'
            elif art_desc:
                summary_html = f'<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">{art_desc}</div>'
                keywords_html = ''
            else:
                summary_html = ''
                keywords_html = ''

            category_cls = "category-finance" if category_label == "Finance" else "category-tech"
            card_html = f'<div class="queue-item"><div style="display: flex; justify-content: space-between; align-items: center;"><div style="display: flex; align-items: center; gap: 0.5rem;"><span style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); min-width: 1.5rem;">#{idx}</span><span class="status-badge {category_cls}">{category_label}</span>{title_html}</div><span class="status-badge {badge_cls}">{art_source}</span></div>{summary_html}{keywords_html}</div>'
            st.markdown(card_html, unsafe_allow_html=True)
    else:
        # Show recent trends from DB if no ranked results
        trends = db.query(Trend).order_by(Trend.discovered_at.desc()).limit(10).all()
        if trends:
            st.markdown("### Recent Trends")
            for trend in trends:
                source_val = trend.source.value if hasattr(trend.source, 'value') else str(trend.source)
                badge_cls = get_source_badge_class(source_val)
                # HTML-escape user content
                safe_title = html.escape(trend.title or '')
                raw_trend_url = trend.article_url or ""
                link_html = (
                    f'<a href="{html.escape(raw_trend_url)}" target="_blank" style="color: var(--accent-primary); text-decoration: none;">{safe_title}</a>'
                    if raw_trend_url and validate_safe_url(raw_trend_url)[0]
                    else f'<span style="color: var(--text-primary);">{safe_title}</span>'
                )

                # Show AI summary if available (escaped)
                if trend.summary:
                    safe_summary = html.escape(trend.summary[:150])
                    summary_html = f'<div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.35rem; line-height: 1.4;">{safe_summary}{"..." if len(trend.summary) > 150 else ""}</div>'
                elif trend.description and len(trend.description) > 10:
                    safe_desc = html.escape(trend.description[:120])
                    summary_html = f'<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">{safe_desc}...</div>'
                else:
                    summary_html = ''

                # Show keywords as small tags (escaped)
                keywords_html = ''
                if trend.keywords and isinstance(trend.keywords, list) and len(trend.keywords) > 0:
                    keywords_tags = ' '.join([f'<span style="background: var(--bg-tertiary); color: var(--text-muted); padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.65rem; margin-right: 0.25rem;">{html.escape(str(kw))}</span>' for kw in trend.keywords[:4]])
                    keywords_html = f'<div style="margin-top: 0.35rem;">{keywords_tags}</div>'

                # Source count indicator
                source_count_html = ''
                if trend.source_count and trend.source_count > 1:
                    source_count_html = f'<span style="background: rgba(34, 197, 94, 0.15); color: #4ADE80; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.65rem; margin-left: 0.5rem;">{trend.source_count} sources</span>'

                card_html = f'<div class="queue-item"><div style="display: flex; justify-content: space-between; align-items: center;">{link_html}<div style="display: flex; align-items: center;">{source_count_html}<span class="status-badge {badge_cls}">{html.escape(source_val)}</span></div></div>{summary_html}{keywords_html}</div>'
                st.markdown(card_html, unsafe_allow_html=True)

    st.markdown("---")

    # ---- Manual Trend Entry ----
    st.markdown("### Add Manual Trend")
    mcol1, mcol2 = st.columns([3, 1])
    with mcol1:
        manual = st.text_input("Trend Title", key="manual_trend", placeholder="Enter trend topic...", max_chars=256)
    with mcol2:
        if st.button("Add Trend", key="add_manual_trend", disabled=not manual, use_container_width=True):
            db.add(Trend(title=manual, source=TrendSource.MANUAL))
            db.commit()
            st.success(f"Added: {manual}")
            rerun_view()


def _render_queue_section(db):
    """Queue section: content list with actions"""
    stats = get_stats(db)

    render_section_header("Queue Workflow", "Translate, review, and approve items ready for publishing.")

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("Translate All", use_container_width=True, disabled=stats['pending'] == 0, key="q_translate"):
            run_batch_translate(db)
    with col2:
        if st.button("Approve All", use_container_width=True, disabled=stats['processed'] == 0, key="q_approve"):
            count = db.query(Tweet).filter(
                Tweet.status == TweetStatus.PROCESSED,
                Tweet.hebrew_draft.isnot(None)
            ).update({Tweet.status: TweetStatus.APPROVED})
            db.commit()
            if count > 0:
                st.success(f"Approved {count}")
                rerun_view()
    with col3:
        status_filter = st.selectbox(
            "Status filter",
            ['all', 'pending', 'processed', 'approved', 'published', 'failed'],
            key="q_filter"
        )
    with col4:
        st.caption(f"Total: {stats['total']} items")

    st.markdown("---")

    tweets = get_tweets(db, status_filter=status_filter, limit=50)

    if not tweets:
        render_empty_state("No content found", "Scrape threads or generate content to populate the queue.")
        return

    for tweet in tweets:
        render_content_item(tweet, db)


def _render_thread_translation(db):
    """Thread Translation section with side-by-side English/Hebrew display."""

    render_section_header("Thread Translation", "Fetch an X thread and translate with side-by-side English/Hebrew review.")

    # Initialize session state for thread translation
    if 'thread_data' not in st.session_state:
        st.session_state.thread_data = None
    if 'thread_translations' not in st.session_state:
        st.session_state.thread_translations = None
    if 'thread_url' not in st.session_state:
        st.session_state.thread_url = ""

    # URL input and fetch button
    col1, col2 = st.columns([4, 1])
    with col1:
        thread_url = st.text_input(
            "Thread URL",
            placeholder="https://x.com/user/status/1234567890",
            key="thread_trans_url",
            value=st.session_state.thread_url,
            max_chars=500
        )
    with col2:
        fetch_btn = st.button("Fetch Thread", type="primary", use_container_width=True, key="fetch_thread_btn")

    # Fetch thread when button clicked
    if fetch_btn and thread_url:
        valid, err = validate_x_url(thread_url)
        if not valid:
            st.error(err)
        elif valid:
            with st.spinner("Fetching thread..."):
                try:
                    from scraper.scraper import TwitterScraper

                    async def fetch():
                        scraper = TwitterScraper()
                        try:
                            await scraper.ensure_logged_in()
                            return await scraper.fetch_raw_thread(thread_url, author_only=True)
                        finally:
                            await scraper.close()

                    result = asyncio.run(fetch())
                    tweets_data = result.get('tweets', [])

                    if tweets_data:
                        st.session_state.thread_data = {
                            'tweets': tweets_data,
                            'author_handle': result.get('author_handle', ''),
                            'author_name': result.get('author_name', ''),
                            'url': thread_url
                        }
                        st.session_state.thread_url = thread_url
                        st.session_state.thread_translations = None
                        st.success(f"Fetched {len(tweets_data)} tweets from thread")
                        rerun_view()
                    else:
                        st.warning("No tweets found in thread")

                except Exception as e:
                    logger.error(f"Failed to fetch thread: {e}")
                    st.error("Failed to fetch thread. Check server logs for details.")

    # Display thread if fetched
    if st.session_state.thread_data:
        thread = st.session_state.thread_data
        tweets = thread.get('tweets', [])
        author = thread.get('author_handle', 'Unknown')

        st.markdown("---")

        # Thread header with author and translate button
        header_col1, header_col2, header_col3 = st.columns([2, 1, 1])
        with header_col1:
            st.markdown(f'<p style="font-weight: 600; color: var(--text-primary);">{html.escape(author)} ({len(tweets)} tweets)</p>', unsafe_allow_html=True)
        with header_col2:
            translation_mode = st.selectbox(
                "Mode",
                ["Consolidated", "Separate"],
                key="trans_mode",
                help="Consolidated: One flowing post. Separate: Keep thread structure."
            )
        with header_col3:
            translate_btn = st.button("Translate to Hebrew", type="primary", use_container_width=True, key="translate_thread_btn")

        # Translate thread when button clicked
        if translate_btn:
            with st.spinner("Translating thread to Hebrew..."):
                try:
                    from processor.processor import ProcessorConfig, TranslationService
                    config = ProcessorConfig()
                    translator = TranslationService(config)

                    if translation_mode == "Consolidated":
                        # Single flowing post
                        hebrew_text = translator.translate_thread_consolidated(tweets)
                        st.session_state.thread_translations = {
                            'mode': 'consolidated',
                            'hebrew': hebrew_text
                        }
                    else:
                        # Separate tweets with context
                        hebrew_list = translator.translate_thread_separate(tweets)
                        st.session_state.thread_translations = {
                            'mode': 'separate',
                            'hebrew_list': hebrew_list
                        }

                    st.success("Translation complete!")
                    rerun_view()

                except Exception as e:
                    logger.error(f"Translation failed: {e}")
                    st.error("Translation failed. Check server logs for details.")

        # Side-by-side display
        st.markdown("---")

        col_en, col_he = st.columns(2)

        translations = st.session_state.thread_translations

        with col_en:
            st.markdown('<div class="translation-panel-header translation-panel-english">English (LTR)</div>', unsafe_allow_html=True)

            if translations and translations.get('mode') == 'consolidated':
                # Show original combined text
                combined_text = "\n\n".join([t.get('text', '') for t in tweets])
                st.markdown(f'<div class="translation-content ltr-container">{html.escape(combined_text)}</div>', unsafe_allow_html=True)
            else:
                # Show individual tweets with numbers
                for idx, tweet in enumerate(tweets, 1):
                    tweet_text = tweet.get('text', '')
                    st.markdown(f'''
                        <div class="thread-tweet-item">
                            <span class="thread-tweet-number">{idx}</span>
                            <span style="color: var(--text-secondary); font-size: 0.85rem;">{html.escape(tweet_text)}</span>
                        </div>
                    ''', unsafe_allow_html=True)

        with col_he:
            st.markdown('<div class="translation-panel-header translation-panel-hebrew">Hebrew (RTL)</div>', unsafe_allow_html=True)

            if translations:
                if translations.get('mode') == 'consolidated':
                    # Show consolidated Hebrew translation
                    hebrew_text = translations.get('hebrew', '')
                    if hebrew_text:
                        st.markdown(f'<div class="translation-content hebrew rtl-container">{html.escape(hebrew_text)}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="translation-content" style="color: var(--text-muted); font-style: italic;">Translation pending...</div>', unsafe_allow_html=True)
                else:
                    # Show individual Hebrew tweets with numbers (RTL)
                    hebrew_list = translations.get('hebrew_list', [])
                    for idx, hebrew_text in enumerate(hebrew_list, 1):
                        if hebrew_text:
                            st.markdown(f'''
                                <div class="thread-tweet-item rtl-container">
                                    <span class="thread-tweet-number rtl">{idx}</span>
                                    <span style="color: var(--text-primary); font-size: 0.85rem;">{html.escape(hebrew_text)}</span>
                                </div>
                            ''', unsafe_allow_html=True)
                        else:
                            st.markdown(f'''
                                <div class="thread-tweet-item rtl-container">
                                    <span class="thread-tweet-number rtl">{idx}</span>
                                    <span style="color: var(--text-muted); font-size: 0.85rem; font-style: italic;">Not translated</span>
                                </div>
                            ''', unsafe_allow_html=True)
            else:
                # Placeholder for Hebrew translations
                for idx in range(1, len(tweets) + 1):
                    st.markdown(f'''
                        <div class="thread-tweet-item rtl-container">
                            <span class="thread-tweet-number rtl">{idx}</span>
                            <span style="color: var(--text-muted); font-size: 0.85rem; font-style: italic;">Click "Translate to Hebrew" to translate</span>
                        </div>
                    ''', unsafe_allow_html=True)

        # Action buttons for translated content
        if translations:
            st.markdown("---")

            action_col1, action_col2, action_col3, action_col4 = st.columns(4)

            with action_col1:
                if st.button("Add to Queue", use_container_width=True, key="add_trans_queue"):
                    try:
                        if translations.get('mode') == 'consolidated':
                            # Add as single consolidated tweet
                            combined_text = "\n\n".join([t.get('text', '') for t in tweets])
                            hebrew_text = translations.get('hebrew', '')

                            if not db.query(Tweet).filter_by(source_url=thread.get('url', '')).first():
                                new_tweet = Tweet(
                                    source_url=thread.get('url', ''),
                                    original_text=combined_text,
                                    hebrew_draft=hebrew_text,
                                    trend_topic=thread.get('author_handle', ''),
                                    status=TweetStatus.PROCESSED if hebrew_text else TweetStatus.PENDING
                                )
                                db.add(new_tweet)
                                db.commit()
                                st.success("Added consolidated thread to queue!")
                            else:
                                st.info("Thread already in queue")
                        else:
                            # Add as separate tweets
                            hebrew_list = translations.get('hebrew_list', [])
                            saved = 0
                            for idx, tweet in enumerate(tweets):
                                permalink = tweet.get('permalink', '')
                                if permalink and not db.query(Tweet).filter_by(source_url=permalink).first():
                                    hebrew_text = hebrew_list[idx] if idx < len(hebrew_list) else None
                                    new_tweet = Tweet(
                                        source_url=permalink,
                                        original_text=tweet.get('text', ''),
                                        hebrew_draft=hebrew_text,
                                        trend_topic=thread.get('author_handle', ''),
                                        status=TweetStatus.PROCESSED if hebrew_text else TweetStatus.PENDING
                                    )
                                    db.add(new_tweet)
                                    saved += 1
                            db.commit()
                            st.success(f"Added {saved} tweets to queue!")

                        rerun_view()

                    except Exception as e:
                        logger.error(f"Failed to add to queue: {e}")
                        st.error("Failed to add to queue. Check server logs for details.")

            with action_col2:
                # Copy Hebrew text button
                if translations.get('mode') == 'consolidated':
                    hebrew_copy = translations.get('hebrew', '')
                else:
                    hebrew_copy = "\n\n".join(translations.get('hebrew_list', []))

                if hebrew_copy:
                    st.download_button(
                        "Download Hebrew",
                        data=hebrew_copy,
                        file_name="hebrew_translation.txt",
                        mime="text/plain",
                        use_container_width=True,
                        key="download_hebrew"
                    )

            with action_col3:
                if st.button("Re-translate", use_container_width=True, key="retranslate_btn"):
                    st.session_state.thread_translations = None
                    rerun_view()

            with action_col4:
                if st.button("Clear Thread", use_container_width=True, key="clear_thread_btn"):
                    st.session_state.thread_data = None
                    st.session_state.thread_translations = None
                    st.session_state.thread_url = ""
                    rerun_view()
    else:
        render_empty_state(
            "No thread loaded",
            'Paste a Twitter/X thread URL above and click "Fetch Thread" to start side-by-side translation.',
        )


def _render_generate_section(db):
    """Generate original Hebrew content from English source material."""

    st.markdown("### Generate Original Hebrew Post")
    st.caption("Paste English source content to generate original Hebrew posts in your voice.")

    # Pre-fill from session state if navigated from trend card
    prefill = st.session_state.get('generate_source_text', '')

    source_text = st.text_area(
        "Source Content (English)",
        value=prefill,
        height=150,
        key="gen_source_text",
        placeholder="Paste English article text, tweet, or news snippet here...",
        max_chars=10000
    )

    # Clear prefill after displaying
    if 'generate_source_text' in st.session_state:
        del st.session_state['generate_source_text']

    col_mode, col_angles, col_btn = st.columns([1, 2, 1])

    with col_mode:
        gen_mode = st.selectbox("Mode", ["Single Post", "Thread"], key="gen_mode")

    with col_angles:
        if gen_mode == "Single Post":
            angle_options = ["All (3 variants)", "News/Breaking", "Educational", "Opinion/Analysis"]
            selected_angle = st.selectbox("Angle", angle_options, key="gen_angle")
        else:
            thread_angle = st.selectbox("Thread Angle", ["Educational", "News/Breaking", "Opinion/Analysis"], key="gen_thread_angle")
            thread_count = st.slider("Tweets in thread", 2, 5, 3, key="gen_thread_count")

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_clicked = st.button("Generate", key="gen_submit", use_container_width=True, type="primary")

    if generate_clicked and source_text and source_text.strip():
        with st.spinner("Generating Hebrew content..."):
            try:
                from processor.content_generator import ContentGenerator
                generator = ContentGenerator()

                if gen_mode == "Single Post":
                    # Map UI selection to angle names
                    angle_map = {
                        "All (3 variants)": None,
                        "News/Breaking": ['news'],
                        "Educational": ['educational'],
                        "Opinion/Analysis": ['opinion'],
                    }
                    angles = angle_map.get(selected_angle)
                    num = 3 if angles is None else 1
                    variants = generator.generate_post(source_text, num_variants=num, angles=angles)
                    st.session_state['gen_variants'] = variants
                    st.session_state['gen_source_for_save'] = source_text
                    st.session_state['gen_mode_result'] = 'post'
                else:
                    angle_name_map = {"Educational": "educational", "News/Breaking": "news", "Opinion/Analysis": "opinion"}
                    thread_tweets = generator.generate_thread(
                        source_text,
                        num_tweets=thread_count,
                        angle=angle_name_map.get(thread_angle, 'educational')
                    )
                    st.session_state['gen_thread_result'] = thread_tweets
                    st.session_state['gen_source_for_save'] = source_text
                    st.session_state['gen_mode_result'] = 'thread'

                rerun_view()
            except Exception as e:
                logger.error(f"Generation failed: {e}")
                st.error("Generation failed. Check server logs for details.")

    # ---- Display generated post variants ----
    if st.session_state.get('gen_mode_result') == 'post' and 'gen_variants' in st.session_state:
        variants = st.session_state['gen_variants']
        source_for_save = st.session_state.get('gen_source_for_save', '')

        st.markdown("---")
        st.markdown("### Generated Variants")
        st.caption("Select a variant, edit if needed, then approve to save.")

        for i, variant in enumerate(variants):
            with st.container():
                col_header, col_status = st.columns([4, 1])
                with col_header:
                    valid_icon = "" if variant.get('is_valid_hebrew') else ""
                    st.markdown(f"**Variant {i+1}: {variant['label']}** {valid_icon}")
                with col_status:
                    st.caption(f"{variant['char_count']} chars")

                # Editable text area with RTL support
                edited = st.text_area(
                    f"Variant {i+1}",
                    value=variant['content'],
                    height=120,
                    key=f"gen_var_{i}",
                )

                # Char counter
                char_count = len(edited) if edited else 0
                over = char_count > 280
                st.markdown(
                    f"<div style='text-align:right; font-size:0.75rem; color: {'var(--accent-danger)' if over else 'var(--text-muted)'};'>"
                    f"{char_count}/280</div>",
                    unsafe_allow_html=True
                )

                col_approve, col_save_draft = st.columns(2)
                with col_approve:
                    if st.button(f"Approve & Save", key=f"gen_approve_{i}", use_container_width=True, type="primary"):
                        import hashlib as _hashlib
                        source_hash = _hashlib.md5(source_for_save.encode()).hexdigest()[:12]
                        new_tweet = Tweet(
                            source_url=f"generated_{source_hash}_{i}",
                            original_text=source_for_save,
                            hebrew_draft=edited,
                            content_type='generation',
                            generation_metadata=json.dumps({
                                'angle': variant['angle'],
                                'label': variant['label'],
                                'source_hash': variant.get('source_hash', ''),
                                'variant_index': i,
                            }),
                            status=TweetStatus.APPROVED
                        )
                        db.add(new_tweet)
                        db.commit()
                        # Auto-style learning
                        if edited and len(edited.strip()) > 30:
                            _auto_learn_style(db, edited.strip())
                        st.success(f"Variant {i+1} approved and saved!")
                        rerun_view()

                with col_save_draft:
                    if st.button(f"Save as Draft", key=f"gen_draft_{i}", use_container_width=True):
                        import hashlib as _hashlib
                        source_hash = _hashlib.md5(source_for_save.encode()).hexdigest()[:12]
                        new_tweet = Tweet(
                            source_url=f"generated_{source_hash}_{i}",
                            original_text=source_for_save,
                            hebrew_draft=edited,
                            content_type='generation',
                            generation_metadata=json.dumps({
                                'angle': variant['angle'],
                                'label': variant['label'],
                                'source_hash': variant.get('source_hash', ''),
                                'variant_index': i,
                            }),
                            status=TweetStatus.PROCESSED
                        )
                        db.add(new_tweet)
                        db.commit()
                        st.success(f"Variant {i+1} saved as draft!")
                        rerun_view()

                st.divider()

        if st.button("Clear Results", key="gen_clear"):
            for k in ['gen_variants', 'gen_source_for_save', 'gen_mode_result']:
                st.session_state.pop(k, None)
            rerun_view()

    # ---- Display generated thread ----
    if st.session_state.get('gen_mode_result') == 'thread' and 'gen_thread_result' in st.session_state:
        thread_tweets = st.session_state['gen_thread_result']
        source_for_save = st.session_state.get('gen_source_for_save', '')

        st.markdown("---")
        st.markdown("### Generated Thread")

        all_edited = []
        for i, tweet_data in enumerate(thread_tweets):
            valid_icon = "" if tweet_data.get('is_valid_hebrew') else ""
            st.markdown(f"**Tweet {tweet_data['index']}/{len(thread_tweets)}** {valid_icon} ({tweet_data['char_count']} chars)")

            edited = st.text_area(
                f"Thread tweet {i+1}",
                value=tweet_data['content'],
                height=80,
                key=f"gen_thread_{i}",
            )
            all_edited.append(edited)

            char_count = len(edited) if edited else 0
            over = char_count > 280
            st.markdown(
                f"<div style='text-align:right; font-size:0.75rem; color: {'var(--accent-danger)' if over else 'var(--text-muted)'};'>"
                f"{char_count}/280</div>",
                unsafe_allow_html=True
            )

        col_approve_thread, col_draft_thread, col_clear_thread = st.columns(3)
        with col_approve_thread:
            if st.button("Approve Thread", key="gen_thread_approve", use_container_width=True, type="primary"):
                import hashlib as _hashlib
                source_hash = _hashlib.md5(source_for_save.encode()).hexdigest()[:12]
                combined = "\n\n---\n\n".join(all_edited)
                new_tweet = Tweet(
                    source_url=f"generated_thread_{source_hash}",
                    original_text=source_for_save,
                    hebrew_draft=combined,
                    content_type='generation',
                    generation_metadata=json.dumps({
                        'type': 'thread',
                        'tweet_count': len(all_edited),
                        'source_hash': source_hash,
                    }),
                    status=TweetStatus.APPROVED
                )
                db.add(new_tweet)
                db.commit()
                if combined and len(combined.strip()) > 30:
                    _auto_learn_style(db, combined.strip())
                st.success("Thread approved and saved!")
                rerun_view()

        with col_draft_thread:
            if st.button("Save as Draft", key="gen_thread_draft", use_container_width=True):
                import hashlib as _hashlib
                source_hash = _hashlib.md5(source_for_save.encode()).hexdigest()[:12]
                combined = "\n\n---\n\n".join(all_edited)
                new_tweet = Tweet(
                    source_url=f"generated_thread_{source_hash}",
                    original_text=source_for_save,
                    hebrew_draft=combined,
                    content_type='generation',
                    generation_metadata=json.dumps({
                        'type': 'thread',
                        'tweet_count': len(all_edited),
                        'source_hash': source_hash,
                    }),
                    status=TweetStatus.PROCESSED
                )
                db.add(new_tweet)
                db.commit()
                st.success("Thread saved as draft!")
                rerun_view()

        with col_clear_thread:
            if st.button("Clear", key="gen_thread_clear", use_container_width=True):
                for k in ['gen_thread_result', 'gen_source_for_save', 'gen_mode_result']:
                    st.session_state.pop(k, None)
                rerun_view()


def render_publish_handoff(db):
    """Publish handoff workflow for approved content."""
    render_section_header("Publish Handoff", "Schedule approved content and mark manual publish outcomes.")

    stats = get_stats(db)
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Ready to publish", stats.get("ready_to_publish", 0))
    with m2:
        st.metric("Scheduled", stats.get("scheduled", 0))
    with m3:
        st.metric("Published", stats.get("published", 0))

    approved_tweets = (
        db.query(Tweet)
        .filter(Tweet.status == TweetStatus.APPROVED)
        .order_by(Tweet.updated_at.desc())
        .limit(50)
        .all()
    )

    if not approved_tweets:
        render_empty_state("No approved items", "Approve drafts in Queue or Generate to prepare publish handoff.")
        return

    st.info("Publishing backend is not enabled yet. Use this section to schedule and track manual posting.")

    for tweet in approved_tweets:
        trend_title = html.escape(tweet.trend_topic or "Untitled")
        preview = html.escape((tweet.hebrew_draft or "")[:180])
        if len(tweet.hebrew_draft or "") > 180:
            preview += "..."
        current_schedule = tweet.scheduled_at
        scheduled_label = current_schedule.strftime("%Y-%m-%d %H:%M UTC") if current_schedule else "Not scheduled"

        with st.container():
            c1, c2, c3 = st.columns([5, 3, 2])
            with c1:
                st.markdown(f"**{trend_title}**")
                st.markdown(f"<div style='direction: rtl; text-align: right; color: var(--text-secondary);'>{preview}</div>", unsafe_allow_html=True)
                st.caption(f"Schedule: {scheduled_label}")
            with c2:
                default_dt = current_schedule or datetime.now(timezone.utc)
                schedule_date = st.date_input(
                    "Schedule date",
                    value=default_dt.date(),
                    key=f"publish_date_{tweet.id}",
                )
                schedule_time = st.time_input(
                    "Schedule time (UTC)",
                    value=default_dt.astimezone(timezone.utc).time().replace(second=0, microsecond=0, tzinfo=None),
                    key=f"publish_time_{tweet.id}",
                )
                if st.button("Set Scheduled Time", key=f"set_schedule_{tweet.id}", use_container_width=True):
                    schedule_dt = datetime.combine(schedule_date, schedule_time, tzinfo=timezone.utc)
                    tweet.scheduled_at = schedule_dt
                    db.commit()
                    push_flash("success", f"Schedule set for item {tweet.id}.", view="content")
                    log_ux_event("set_scheduled_time", "content", success=True, metadata={"tweet_id": tweet.id})
                    rerun_view()
            with c3:
                if st.button("Mark as Published", key=f"mark_published_{tweet.id}", use_container_width=True, type="primary"):
                    tweet.status = TweetStatus.PUBLISHED
                    tweet.scheduled_at = None
                    db.commit()
                    push_flash("success", f"Item {tweet.id} marked as published.", view="content")
                    log_ux_event("mark_published", "content", success=True, metadata={"tweet_id": tweet.id})
                    rerun_view()

                if st.button("Return to Review", key=f"return_review_{tweet.id}", use_container_width=True):
                    tweet.status = TweetStatus.PROCESSED
                    tweet.scheduled_at = None
                    db.commit()
                    push_flash("warning", f"Item {tweet.id} returned to review.", view="content")
                    log_ux_event("return_to_review", "content", success=True, metadata={"tweet_id": tweet.id})
                    rerun_view()
        st.divider()


def render_content_item(tweet, db):
    """Render a content list item with media indicators"""
    status_str = format_status_str(tweet.status)
    media_count, media_label = parse_media_info(tweet.media_paths)

    with st.container():
        col1, col2, col3 = st.columns([4, 1, 1])

        with col1:
            # SAFETY: trend_topic and original_text are user-derived, must escape
            st.markdown(f"""
                <div style="padding: 0.5rem 0;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-weight: 500; color: var(--text-primary);">{html.escape(tweet.trend_topic or 'Unknown')}</span>
                        <span class="status-badge status-{status_str.lower()}">{html.escape(status_str)}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 0.25rem;">
                        {html.escape(tweet.original_text[:120])}...
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with col2:
            if media_count > 0:
                st.markdown(f"""
                    <div style="font-size: 0.75rem; color: var(--accent-primary); text-align: center;">
                        {media_label} ({media_count})
                    </div>
                """, unsafe_allow_html=True)
            elif tweet.hebrew_draft:
                st.markdown(f"""
                    <div style="font-size: 0.75rem; color: var(--accent-success); direction: rtl; text-align: right;">
                        Translated
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.caption("Not translated")

        with col3:
            if st.button("Edit", key=f"edit_{tweet.id}", use_container_width=True):
                set_selected_item(tweet.id)
                rerun_view()

        st.markdown("<hr style='margin: 0.5rem 0; border-color: var(--border-default);'>", unsafe_allow_html=True)


def _auto_learn_style(db, hebrew_text: str, source_url: str = None):
    """Auto-add approved Hebrew content to style examples for learning."""
    try:
        sm = get_style_manager()
        if not sm:
            return
        # Check minimum Hebrew content
        if not sm.is_hebrew_content(hebrew_text, min_ratio=0.5):
            return
        word_count = sm.count_words(hebrew_text)
        if word_count < 10:
            return
        # Avoid duplicates: check if content already exists
        existing = db.query(StyleExample).filter(
            StyleExample.content == hebrew_text,
            StyleExample.is_active == True
        ).first()
        if existing:
            return
        # Extract topic tags using fallback (no API call on approval)
        tags = sm._fallback_topic_tags(hebrew_text)
        sm.add_style_example(
            db, hebrew_text,
            source_type='approved',
            source_url=source_url,
            topic_tags=tags
        )
        # Record positive feedback on related style examples
        _record_style_feedback(db, tags, approved=True)
        logger.info(f"Auto-learned style from approved content ({word_count} words)")
    except Exception as e:
        logger.warning(f"Auto-style learning failed: {e}")


def _record_style_feedback(db, tags: list, approved: bool):
    """Propagate approval/rejection feedback to matching style examples."""
    try:
        sm = get_style_manager()
        if not sm or not tags:
            return
        matching = sm.find_examples_by_tag_overlap(db, tags, limit=3)
        for ex in matching:
            sm.record_feedback(db, ex.id, approved)
    except Exception as e:
        logger.warning(f"Style feedback recording failed: {e}")


def render_editor(db, tweet_id):
    """Full editor for a single tweet"""
    tweet = db.query(Tweet).filter(Tweet.id == tweet_id).first()

    if not tweet:
        st.error("Item not found")
        set_selected_item(None)
        return

    status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)

    # Top navigation
    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        if st.button("< Back", use_container_width=True):
            set_selected_item(None)
            rerun_view()

    with col2:
        st.markdown(f"""
            <div style="text-align: center; padding: 0.5rem;">
                <span style="font-weight: 600; font-size: 1rem; color: var(--text-primary);">{html.escape(tweet.trend_topic or 'Unknown')}</span>
                <span class="status-badge status-{html.escape(status_str.lower())}" style="margin-left: 0.75rem;">{html.escape(status_str)}</span>
            </div>
        """, unsafe_allow_html=True)

    with col3:
        if tweet.source_url and validate_safe_url(tweet.source_url)[0]:
            st.markdown(f"[View on X]({html.escape(tweet.source_url)})")

    st.markdown("---")

    # Side-by-side content
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
            <div style="background: var(--bg-tertiary); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem;">
                <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Original (English)</span>
            </div>
        """, unsafe_allow_html=True)

        st.text_area(
            "Original",
            value=tweet.original_text,
            height=250,
            disabled=True,
            key="edit_original",
        )

    with col2:
        st.markdown("""
            <div style="background: rgba(63, 185, 80, 0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem;">
                <span style="font-size: 0.75rem; font-weight: 600; color: var(--accent-success); text-transform: uppercase;">Hebrew Translation</span>
            </div>
        """, unsafe_allow_html=True)

        hebrew = st.text_area(
            "Hebrew",
            value=tweet.hebrew_draft or "",
            height=250,
            key="edit_hebrew",
            placeholder="Enter Hebrew translation..."
        )

        # Character count
        char_count = len(hebrew) if hebrew else 0
        pct = min((char_count / 280) * 100, 100)
        bar_color = "var(--accent-success)" if char_count <= 280 else "var(--accent-danger)"

        st.markdown(f"""
            <div style="margin-top: 0.5rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                    <span style="font-size: 0.7rem; color: var(--text-muted);">Characters</span>
                    <span style="font-size: 0.75rem; font-weight: 600; color: var(--text-primary);">{char_count}/280</span>
                </div>
                <div style="background: var(--bg-elevated); border-radius: 4px; height: 4px; overflow: hidden;">
                    <div style="background: {bar_color}; width: {pct}%; height: 100%;"></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Media Gallery Section (if media exists)
    if tweet.media_paths:
        try:
            import json as json_mod
            from pathlib import Path
            media_list = json_mod.loads(tweet.media_paths)

            if media_list:
                st.markdown("---")
                st.markdown(f"""
                    <div style="background: var(--bg-tertiary); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.75rem; font-weight: 600; color: var(--accent-primary); text-transform: uppercase;">
                            Thread Media ({len(media_list)} files)
                        </span>
                    </div>
                """, unsafe_allow_html=True)

                num_cols = min(len(media_list), 4)
                cols = st.columns(num_cols)

                for idx, media_item in enumerate(media_list):
                    with cols[idx % num_cols]:
                        media_type = media_item.get('type', 'unknown')
                        local_path = media_item.get('local_path', '')

                        if local_path and Path(local_path).exists():
                            if media_type == 'photo':
                                st.image(local_path, caption=f"Tweet #{idx+1}")
                            elif media_type == 'video':
                                st.video(local_path)
                                st.caption(f"Video #{idx+1}")
                        else:
                            st.markdown(f"""
                                <div style="background: var(--bg-elevated); padding: 1rem; border-radius: 8px; text-align: center; color: var(--text-muted);">
                                    {media_type.title()} missing<br>
                                    <small>File not found</small>
                                </div>
                            """, unsafe_allow_html=True)
        except Exception as e:
            logger.warning(f"Failed to parse media_paths: {e}")

    # Action buttons
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        if st.button("Save", key="ed_save", use_container_width=True, type="primary"):
            update_tweet(db, tweet.id, hebrew_draft=hebrew)
            st.success("Saved!")
            rerun_view()

    with col2:
        if st.button("Translate", key="ed_trans", use_container_width=True):
            with st.spinner("Translating..."):
                try:
                    from processor.processor import ProcessorConfig, TranslationService
                    config = ProcessorConfig()
                    translator = TranslationService(config)
                    translation = translator.translate_text(tweet.original_text)
                    if translation:
                        update_tweet(db, tweet.id, hebrew_draft=translation, status=TweetStatus.PROCESSED)
                        st.success("Done!")
                    else:
                        st.error("Empty translation")
                except Exception as e:
                    logger.error(f"Editor translation failed: {e}")
                    st.error("Translation failed. Check server logs.")
            rerun_view()

    with col3:
        if tweet.status != TweetStatus.APPROVED:
            if st.button("Approve", key="ed_approve", use_container_width=True):
                update_tweet(db, tweet.id, status=TweetStatus.APPROVED, hebrew_draft=hebrew)
                # Auto-style learning: add approved Hebrew content to style examples
                if hebrew and len(hebrew.strip()) > 30:
                    _auto_learn_style(db, hebrew.strip(), tweet.source_url)
                st.success("Approved!")
                set_selected_item(None)
                rerun_view()

    with col4:
        if st.button("Reset", key="ed_reset", use_container_width=True):
            update_tweet(db, tweet.id, status=TweetStatus.PENDING)
            rerun_view()

    with col5:
        if st.button("Delete", key="ed_delete", use_container_width=True):
            delete_tweet(db, tweet.id)
            set_selected_item(None)
            rerun_view()

    # Error display
    if tweet.status == TweetStatus.FAILED and tweet.error_message:
        st.error("Processing failed for this item. Check server logs for details.")


_MAX_BATCH_SIZE = 20


def run_batch_translate(db):
    """Run batch translation (max 20 per batch)."""
    all_pending = db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).count()
    pending = db.query(Tweet).filter(Tweet.status == TweetStatus.PENDING).limit(_MAX_BATCH_SIZE).all()

    if not pending:
        st.info("No pending items to translate")
        return

    if all_pending > _MAX_BATCH_SIZE:
        st.warning(f"{all_pending} pending items — translating first {_MAX_BATCH_SIZE}. Run again for more.")

    progress = st.progress(0)
    status_text = st.empty()

    try:
        from processor.processor import ProcessorConfig, TranslationService
        config = ProcessorConfig()
        translator = TranslationService(config)

        success = 0
        _BATCH_COMMIT_SIZE = 5
        for idx, tweet in enumerate(pending):
            status_text.text(f"Translating {idx + 1}/{len(pending)}...")
            progress.progress((idx + 1) / len(pending))

            try:
                translation = translator.translate_text(tweet.original_text)
                if translation:
                    tweet.hebrew_draft = translation
                    tweet.status = TweetStatus.PROCESSED
                    success += 1
                else:
                    tweet.status = TweetStatus.FAILED
                    tweet.error_message = "Empty translation"
            except Exception as e:
                tweet.status = TweetStatus.FAILED
                tweet.error_message = str(e)[:500]

            if (idx + 1) % _BATCH_COMMIT_SIZE == 0:
                db.commit()

        db.commit()  # final commit for remaining items

        progress.empty()
        status_text.empty()
        st.success(f"Translated {success}/{len(pending)} items")
        rerun_view()

    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        st.error("Translation error. Check server logs for details.")
