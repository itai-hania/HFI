import streamlit as st
import html
import json
import time
import asyncio
import logging
from pathlib import Path
from sqlalchemy import cast, String, func
from common.models import Tweet, Trend, Thread, StyleExample
from dashboard.lazy_loaders import get_style_manager
from dashboard.validators import validate_x_url

logger = logging.getLogger(__name__)


def render_settings(db):
    """Settings and configuration"""

    st.markdown("""
        <div class="page-header">
            <h1 class="page-title">Settings</h1>
            <p class="page-subtitle">Configuration and database management</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Database Stats")

        tweet_count = db.query(Tweet).count()
        thread_count = db.query(Thread).count()
        trend_count = db.query(Trend).count()

        st.metric("Total Tweets", tweet_count)
        st.metric("Total Threads", thread_count)
        st.metric("Total Trends", trend_count)

        st.markdown("---")

        # ---- Glossary Editor ----
        st.markdown("### Glossary Editor")
        glossary_path = Path(__file__).parent.parent.parent / "config" / "glossary.json"
        try:
            glossary_data = json.loads(glossary_path.read_text(encoding='utf-8')) if glossary_path.exists() else {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load glossary: {e}")
            glossary_data = {}
        edited_glossary = st.text_area(
            "Glossary (JSON)",
            json.dumps(glossary_data, indent=2, ensure_ascii=False),
            height=200,
            key="glossary_editor",
            max_chars=50000
        )
        if st.button("Save Glossary", key="save_glossary", use_container_width=True):
            try:
                parsed = json.loads(edited_glossary)
                # Validate structure: must be dict[str, str]
                if not isinstance(parsed, dict):
                    st.error("Glossary must be a JSON object (not array).")
                elif not all(isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()):
                    st.error("Glossary values must all be strings.")
                elif len(edited_glossary.encode('utf-8')) > 1_000_000:
                    st.error("Glossary too large (max 1MB).")
                else:
                    # Backup current glossary before overwriting
                    if glossary_path.exists():
                        backup_path = glossary_path.with_suffix('.json.bak')
                        import shutil
                        shutil.copy2(glossary_path, backup_path)
                    glossary_path.parent.mkdir(parents=True, exist_ok=True)
                    glossary_path.write_text(edited_glossary, encoding='utf-8')
                    st.success("Glossary saved!")
            except json.JSONDecodeError:
                st.error("Invalid JSON. Please fix and try again.")

    # ==========================================
    # STYLE LEARNING SYSTEM (Full Width)
    # ==========================================
    st.markdown("---")
    st.markdown("### Style Learning System")
    st.markdown('<p style="color: var(--text-secondary); font-size: 0.85rem;">Import your Hebrew writing samples for style-matched translations.</p>', unsafe_allow_html=True)

    sm = get_style_manager()

    # Get statistics
    if sm:
        stats = sm.get_example_stats(db)
        example_count = stats['count']
        total_words = stats['total_words']
        topics = stats['topics']
    else:
        example_count = db.query(StyleExample).filter(StyleExample.is_active == True).count()
        total_words = 0
        topics = []

    # Stats row
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    with stat_col1:
        st.metric("Examples", example_count)
    with stat_col2:
        st.metric("Total Words", f"{total_words:,}")
    with stat_col3:
        st.metric("Topics", len(topics))
    with stat_col4:
        if example_count >= 100:
            st.warning("100+ examples")
        elif example_count >= 50:
            st.info("Good coverage")
        elif example_count > 0:
            st.caption("Add more examples")
        else:
            st.caption("No examples yet")

    # Soft limit warning
    if example_count >= 100:
        st.info("You have 100+ examples. This provides excellent style coverage, but you can still add more if needed.")

    # Import section
    import_col1, import_col2 = st.columns(2)

    with import_col1:
        st.markdown("#### Import from X Thread")
        thread_url_import = st.text_input(
            "Thread URL",
            placeholder="https://x.com/user/status/123...",
            key="style_import_url",
            label_visibility="collapsed",
            max_chars=500
        )
        if st.button("Fetch Thread", key="import_x_thread", use_container_width=True, disabled=not thread_url_import):
            valid, err = validate_x_url(thread_url_import)
            if not valid:
                st.error(err)
            elif valid:
                with st.spinner("Fetching thread..."):
                    try:
                        from scraper.scraper import TwitterScraper

                        async def fetch_for_style():
                            scraper = TwitterScraper()
                            try:
                                await scraper.ensure_logged_in()
                                return await scraper.fetch_raw_thread(thread_url_import, author_only=True)
                            finally:
                                await scraper.close()

                        result = asyncio.run(fetch_for_style())
                        tweets_data = result.get('tweets', [])

                        if tweets_data:
                            all_text = "\n\n".join([t.get('text', '') for t in tweets_data if t.get('text')])

                            if sm and sm.is_hebrew_content(all_text, min_ratio=0.5):
                                tags = sm.extract_topic_tags(all_text)
                                st.session_state.style_import_preview = all_text
                                st.session_state.style_import_tags = tags
                                st.session_state.style_import_tweet_count = len(tweets_data)
                                st.rerun()
                            else:
                                st.warning("Thread doesn't contain enough Hebrew content (need >50%)")
                        else:
                            st.warning("No tweets found in thread")
                    except Exception as e:
                        logger.error(f"Style import failed: {e}")
                        st.error("Import failed. Check server logs for details.")

        # Preview fetched thread before saving
        if st.session_state.get('style_import_preview'):
            preview_text = st.session_state.style_import_preview
            preview_tags = st.session_state.get('style_import_tags', [])
            tweet_count = st.session_state.get('style_import_tweet_count', 0)
            st.text_area("Preview", preview_text[:500] + ("..." if len(preview_text) > 500 else ""), height=100, disabled=True, key="x_thread_preview_area")
            edited_tags = st.text_input("Edit Tags (comma-separated)", value=", ".join(preview_tags), key="x_thread_edit_tags")
            pcol1, pcol2 = st.columns(2)
            with pcol1:
                if st.button("Save Example", key="confirm_x_import", use_container_width=True):
                    final_tags = [t.strip() for t in edited_tags.split(",") if t.strip()]
                    example = sm.add_style_example(
                        db,
                        content=preview_text,
                        source_type='x_thread',
                        source_url=thread_url_import,
                        topic_tags=final_tags
                    )
                    if example:
                        st.success(f"Imported {tweet_count} tweets as style example")
                    else:
                        st.error("Failed to save example")
                    st.session_state.pop('style_import_preview', None)
                    st.session_state.pop('style_import_tags', None)
                    st.session_state.pop('style_import_tweet_count', None)
                    st.rerun()
            with pcol2:
                if st.button("Cancel", key="cancel_x_import", use_container_width=True):
                    st.session_state.pop('style_import_preview', None)
                    st.session_state.pop('style_import_tags', None)
                    st.session_state.pop('style_import_tweet_count', None)
                    st.rerun()

    with import_col2:
        st.markdown("#### Upload Local File")
        uploaded_file = st.file_uploader(
            "Upload .txt or .md file",
            type=['txt', 'md'],
            key="style_file_upload",
            label_visibility="collapsed"
        )
        if uploaded_file:
            file_content = uploaded_file.read().decode('utf-8')
            if sm and sm.is_hebrew_content(file_content, min_ratio=0.5):
                st.text_area("Preview", file_content[:500] + ("..." if len(file_content) > 500 else ""), height=100, disabled=True)
                file_tags = sm.extract_topic_tags(file_content) if sm else ['fintech']
                edited_file_tags = st.text_input("Edit Tags (comma-separated)", value=", ".join(file_tags), key="file_edit_tags")
                if st.button("Add to Style Examples", key="add_uploaded_file", use_container_width=True):
                    final_tags = [t.strip() for t in edited_file_tags.split(",") if t.strip()]
                    example = sm.add_style_example(
                        db,
                        content=file_content,
                        source_type='local_file',
                        source_url=uploaded_file.name,
                        topic_tags=final_tags
                    ) if sm else None
                    if example:
                        st.success(f"Added file as style example (tags: {', '.join(final_tags[:3])})")
                        st.rerun()
            else:
                st.warning("File doesn't contain enough Hebrew content (need >50%)")

    # Manual entry
    st.markdown("#### Add Manual Example")
    manual_content = st.text_area(
        "Hebrew Text",
        placeholder="הקלד כאן טקסט עברי לדוגמה...",
        height=100,
        key="manual_style_input",
        label_visibility="collapsed",
        max_chars=10000
    )
    if manual_content and sm and sm.is_hebrew_content(manual_content, min_ratio=0.5):
        manual_auto_tags = sm.extract_topic_tags(manual_content)
        edited_manual_tags = st.text_input("Edit Tags (comma-separated)", value=", ".join(manual_auto_tags), key="manual_edit_tags")
    else:
        edited_manual_tags = ""
    manual_col1, manual_col2 = st.columns([3, 1])
    with manual_col2:
        if st.button("Add Example", key="add_manual_style", use_container_width=True, disabled=not manual_content):
            if sm and sm.is_hebrew_content(manual_content, min_ratio=0.5):
                final_tags = [t.strip() for t in edited_manual_tags.split(",") if t.strip()] if edited_manual_tags else ['fintech']
                example = sm.add_style_example(
                    db,
                    content=manual_content,
                    source_type='manual',
                    topic_tags=final_tags
                )
                if example:
                    st.success(f"Added manual example (tags: {', '.join(final_tags[:3])})")
                    st.rerun()
            else:
                st.warning("Text doesn't contain enough Hebrew (need >50%)")

    # Export button
    st.markdown("---")
    export_col1, export_col2 = st.columns([3, 1])
    with export_col2:
        if example_count > 0 and sm:
            export_data = sm.export_to_json(db)
            st.download_button(
                "Export Examples (JSON)",
                export_data,
                "style_examples.json",
                mime="application/json",
                use_container_width=True
            )

    # Examples list with search/filter
    if example_count > 0:
        st.markdown("#### Your Style Examples")

        # Topic tag filter
        filter_col1, filter_col2 = st.columns([3, 1])
        with filter_col1:
            if topics:
                selected_tag = st.selectbox("Filter by topic", ["All"] + sorted(topics), key="style_tag_filter")
            else:
                selected_tag = "All"

        # Pagination state
        if 'style_examples_limit' not in st.session_state:
            st.session_state.style_examples_limit = 20

        display_limit = st.session_state.style_examples_limit

        # Query with optional tag filter
        query = db.query(StyleExample).filter(StyleExample.is_active == True).order_by(StyleExample.created_at.desc())

        if selected_tag != "All":
            # JSON array string match (case-insensitive), e.g. ["fintech","ai"].
            normalized_tag = selected_tag.lower()
            tag_pattern = f'%"{normalized_tag}"%'
            filtered_query = query.filter(
                func.lower(cast(StyleExample.topic_tags, String)).like(tag_pattern)
            )
            filtered_count = filtered_query.count()
            examples = filtered_query.limit(display_limit).all()
        else:
            examples = query.limit(display_limit).all()
            filtered_count = example_count

        for ex in examples:
            source_label = html.escape({'x_thread': 'X Thread', 'local_file': 'File', 'manual': 'Manual'}.get(ex.source_type, ex.source_type or 'unknown'))
            tags_str = html.escape(', '.join(ex.topic_tags[:3]) if ex.topic_tags else 'No tags')
            preview = html.escape(ex.content[:100]) + ('...' if len(ex.content) > 100 else '')

            # Check if this example is being edited
            is_editing = st.session_state.get(f'editing_style_{ex.id}', False)

            if is_editing:
                st.markdown(f"**Editing Example #{ex.id}**")
                new_content = st.text_area("Content", value=ex.content, height=150, key=f"edit_content_{ex.id}")
                current_tags = ', '.join(ex.topic_tags) if ex.topic_tags else ''
                new_tags_str = st.text_input("Tags (comma-separated)", value=current_tags, key=f"edit_tags_{ex.id}")
                edit_btn_col1, edit_btn_col2 = st.columns(2)
                with edit_btn_col1:
                    if st.button("Save", key=f"save_edit_{ex.id}", use_container_width=True):
                        new_tags = [t.strip() for t in new_tags_str.split(",") if t.strip()]
                        if sm:
                            sm.update_example(db, ex.id, content=new_content, topic_tags=new_tags)
                        st.session_state[f'editing_style_{ex.id}'] = False
                        st.rerun()
                with edit_btn_col2:
                    if st.button("Cancel", key=f"cancel_edit_{ex.id}", use_container_width=True):
                        st.session_state[f'editing_style_{ex.id}'] = False
                        st.rerun()
            else:
                ex_col1, ex_col2, ex_col3 = st.columns([5, 1, 1])
                with ex_col1:
                    st.markdown(f"""
                        <div class="queue-item" style="padding: 0.75rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="font-size: 0.8rem; font-weight: 500; color: var(--text-primary);">#{ex.id}</span>
                                <div>
                                    <span class="status-badge source-manual" style="font-size: 0.6rem;">{source_label}</span>
                                    <span style="font-size: 0.7rem; color: var(--text-muted); margin-left: 0.5rem;">{ex.word_count} words</span>
                                </div>
                            </div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem; direction: rtl; text-align: right;">{preview}</div>
                            <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 0.25rem;">Tags: {tags_str}</div>
                        </div>
                    """, unsafe_allow_html=True)
                with ex_col2:
                    if st.button("Edit", key=f"edit_style_{ex.id}", help="Edit this example"):
                        st.session_state[f'editing_style_{ex.id}'] = True
                        st.rerun()
                with ex_col3:
                    if st.button("🗑️", key=f"del_style_{ex.id}", help="Delete this example"):
                        if sm:
                            sm.delete_example(db, ex.id)
                            st.rerun()

        # Load More pagination
        if filtered_count > display_limit:
            st.caption(f"Showing {min(display_limit, len(examples))} of {filtered_count} examples")
            if st.button("Load More", key="load_more_examples", use_container_width=True):
                st.session_state.style_examples_limit = display_limit + 20
                st.rerun()
        elif len(examples) > 0 and filtered_count > len(examples):
            st.caption(f"Showing {len(examples)} of {filtered_count} examples")

    st.markdown("---")

    # ---- Autopilot Defaults ----
    st.markdown("### Autopilot Defaults")
    st.markdown('<p style="color: var(--text-secondary); font-size: 0.85rem;">Configure defaults for the two-phase autopilot pipeline.</p>', unsafe_allow_html=True)

    ap_col1, ap_col2, ap_col3 = st.columns(3)
    with ap_col1:
        ap_top_n = st.slider(
            "Trends to auto-select",
            min_value=1, max_value=5,
            value=st.session_state.get('autopilot_top_n', 3),
            key="ap_top_n_slider",
        )
        st.session_state.autopilot_top_n = ap_top_n
    with ap_col2:
        angle_options = ['news', 'educational', 'opinion']
        current_angle = st.session_state.get('autopilot_angle', 'news')
        ap_angle = st.selectbox(
            "Default content angle",
            angle_options,
            index=angle_options.index(current_angle) if current_angle in angle_options else 0,
            key="ap_angle_select",
        )
        st.session_state.autopilot_angle = ap_angle
    with ap_col3:
        ap_summarize = st.checkbox(
            "Auto-summarize",
            value=st.session_state.get('autopilot_auto_summarize', True),
            key="ap_summarize_check",
            help="Generate AI summaries during Phase A",
        )
        st.session_state.autopilot_auto_summarize = ap_summarize

    st.markdown("---")

    with col2:
        st.markdown("### Status Guide")

        statuses = [
            ('PENDING', 'Inbox - awaiting translation'),
            ('PROCESSED', 'Drafted - needs review'),
            ('APPROVED', 'Ready - approved for publishing'),
            ('PUBLISHED', 'Published - posted to X'),
            ('FAILED', 'Failed - error occurred'),
        ]

        for status, desc in statuses:
            st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0;">
                    <span class="status-badge status-{status.lower()}">{status}</span>
                    <span style="color: var(--text-secondary); font-size: 0.85rem;">{desc}</span>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        st.markdown("### Workflow")
        st.markdown("""
        1. **Scrape** - Fetch threads from X
        2. **Translate** - Auto or manual translation
        3. **Review** - Edit and approve drafts
        4. **Publish** - Post to X (coming soon)
        """)

        st.markdown("---")

        # ---- Data Export (reuse counts from top of render_settings) ----
        st.markdown("### Data Export")
        tweets_export = json.dumps(
            [{"id": t.id, "text": t.original_text, "hebrew": t.hebrew_draft, "status": t.status.value}
             for t in db.query(Tweet).yield_per(100)],
            indent=2, ensure_ascii=False)
        st.download_button(f"Export Tweets (JSON) ({tweet_count})", tweets_export, "tweets.json", mime="application/json", use_container_width=True)

        trends_export = json.dumps(
            [{"title": t.title, "source": t.source.value, "description": t.description}
             for t in db.query(Trend).yield_per(100)],
            indent=2, ensure_ascii=False)
        st.download_button(f"Export Trends (JSON) ({trend_count})", trends_export, "trends.json", mime="application/json", use_container_width=True)

    st.markdown("---")

    # ---- Danger Zone ----
    st.markdown("### Danger Zone")
    with st.expander("Destructive Actions"):
        st.warning("These actions cannot be undone")
        confirm = st.checkbox("I understand this cannot be undone", key="danger_confirm")

        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            if st.button("Delete All Tweets", use_container_width=True, disabled=not confirm):
                db.query(Tweet).delete()
                db.commit()
                st.success("Deleted all tweets")
                st.rerun()
        with dcol2:
            if st.button("Delete All Threads", use_container_width=True, disabled=not confirm):
                db.query(Thread).delete()
                db.commit()
                st.success("Deleted all threads")
                st.rerun()
        with dcol3:
            if st.button("Delete All Trends", use_container_width=True, disabled=not confirm):
                db.query(Trend).delete()
                db.commit()
                st.success("Deleted all trends")
                st.rerun()
