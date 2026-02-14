import streamlit as st
import html
import time
from common.models import Tweet, Trend, TweetStatus
from dashboard.db_helpers import get_stats, delete_trend
from dashboard.helpers import get_source_badge_class
from dashboard.validators import validate_safe_url


def render_home(db):
    """Home - overview of processed content and discovered trends"""

    st.markdown("""
        <div class="page-header">
            <h1 class="page-title">Home</h1>
            <p class="page-subtitle">Your processed content and discovered trends</p>
        </div>
    """, unsafe_allow_html=True)

    stats = get_stats(db)

    # Pipeline stats row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card stat-inbox"><div class="stat-value">{stats["pending"]}</div><div class="stat-label">Inbox</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card stat-drafts"><div class="stat-value">{stats["processed"]}</div><div class="stat-label">Drafts</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card stat-ready"><div class="stat-value">{stats["approved"]}</div><div class="stat-label">Ready</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card stat-published"><div class="stat-value">{stats["published"]}</div><div class="stat-label">Published</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Ready to Publish Queue ---
    approved_tweets = db.query(Tweet).filter(
        Tweet.status == TweetStatus.APPROVED
    ).order_by(Tweet.updated_at.desc()).limit(10).all()

    if approved_tweets:
        if 'home_publish_expanded' not in st.session_state:
            st.session_state.home_publish_expanded = True

        publish_expanded = st.checkbox(
            f"Ready to Publish ({len(approved_tweets)})",
            value=st.session_state.home_publish_expanded,
            key="publish_section_toggle"
        )
        st.session_state.home_publish_expanded = publish_expanded

        if publish_expanded:
            for tweet in approved_tweets:
                preview = html.escape((tweet.hebrew_draft or '')[:80])
                if len(tweet.hebrew_draft or '') > 80:
                    preview += '...'
                trend_title = html.escape(tweet.trend_topic or 'Unknown')
                updated = tweet.updated_at.strftime('%Y-%m-%d %H:%M') if tweet.updated_at else ''
                batch_label = ''
                if tweet.pipeline_batch_id:
                    batch_label = f'<span style="background: rgba(25, 154, 245, 0.1); color: var(--accent-primary); padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.6rem; margin-left: 0.5rem;">pipeline</span>'

                with st.container():
                    pub_col1, pub_col2 = st.columns([5, 1])
                    with pub_col1:
                        st.markdown(f"""
                            <div style="padding: 0.4rem 0;">
                                <div style="display: flex; align-items: center; gap: 0.5rem;">
                                    <span style="font-size: 0.8rem; font-weight: 500; color: var(--text-primary);">{trend_title}</span>
                                    {batch_label}
                                </div>
                                <div style="font-size: 0.8rem; color: var(--text-secondary); direction: rtl; text-align: right; margin-top: 0.25rem;">{preview}</div>
                                <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 0.15rem;">Approved {updated}</div>
                            </div>
                        """, unsafe_allow_html=True)
                    with pub_col2:
                        if st.button("Edit", key=f"pub_edit_{tweet.id}", use_container_width=True):
                            st.session_state.selected_item = tweet.id
                            st.session_state.current_view = 'content'
                            st.rerun()
                    st.markdown("<hr style='margin: 0.25rem 0; border-color: var(--border-default);'>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================================================
    # PHASE 4: Full-width rows with collapsible sections (using session state)
    # ==========================================================================

    # Initialize section toggle states
    if 'home_trends_expanded' not in st.session_state:
        st.session_state.home_trends_expanded = True
    if 'home_threads_expanded' not in st.session_state:
        st.session_state.home_threads_expanded = True

    # --- Section 1: Discovered Trends (Full Width) ---
    trends = db.query(Trend).order_by(Trend.discovered_at.desc()).limit(15).all()
    trends_count = len(trends)

    # Collapsible section using checkbox styled as header
    trends_expanded = st.checkbox(
        f"📰 Discovered Trends ({trends_count})",
        value=st.session_state.home_trends_expanded,
        key="trends_section_toggle"
    )
    st.session_state.home_trends_expanded = trends_expanded

    if trends_expanded:
        if trends:
            for idx, trend in enumerate(trends):
                source_val = trend.source.value if hasattr(trend.source, 'value') else str(trend.source)
                badge_cls = get_source_badge_class(source_val)
                safe_title = html.escape(trend.title or '')

                # Check if already in queue
                in_queue = db.query(Tweet).filter(Tweet.trend_topic == trend.title).first() is not None

                # Summary (more room now - full width)
                summary_text = ''
                if trend.summary:
                    summary_text = html.escape(trend.summary[:250]) + ('...' if len(trend.summary) > 250 else '')
                elif trend.description and len(trend.description) > 10:
                    summary_text = html.escape(trend.description[:200]) + '...'

                # Full-width trend card using st.container
                with st.container():
                    # Main card row - title, badge, generate, queue, delete buttons
                    card_col1, card_col2, card_col_gen, card_col3, card_col4 = st.columns([4, 1, 1, 1, 0.5])
                    with card_col1:
                        # Title with rank
                        if trend.article_url and validate_safe_url(trend.article_url)[0]:
                            st.markdown(f"**#{idx + 1}** [{safe_title}]({html.escape(trend.article_url)})")
                        else:
                            st.markdown(f"**#{idx + 1}** {safe_title}")
                        # Summary
                        if summary_text:
                            st.caption(summary_text)
                        # Keywords
                        if trend.keywords and isinstance(trend.keywords, list) and len(trend.keywords) > 0:
                            st.markdown(f"🏷️ {', '.join(trend.keywords[:5])}")
                    with card_col2:
                        # Source badge
                        st.markdown(f'<span class="status-badge {badge_cls}">{html.escape(source_val)}</span>', unsafe_allow_html=True)
                        if trend.source_count and trend.source_count > 1:
                            st.caption(f"{trend.source_count} sources")
                    with card_col_gen:
                        if st.button("Generate", key=f"home_gen_{trend.id}", use_container_width=True):
                            # Pre-fill source text and navigate to Content > Generate
                            source = f"{trend.title}\n\n{trend.description or trend.summary or ''}"
                            st.session_state['generate_source_text'] = source.strip()
                            st.session_state.current_view = 'content'
                            st.rerun()

                    with card_col3:
                        # Queue button in same row
                        if in_queue:
                            st.success("✓ In Queue")
                        else:
                            if st.button("+ Queue", key=f"home_add_trend_{trend.id}", use_container_width=True):
                                new_tweet = Tweet(
                                    source_url=trend.article_url or f"trend_{trend.id}",
                                    original_text=f"{trend.title}\n\n{trend.description or trend.summary or ''}",
                                    trend_topic=trend.title,
                                    status=TweetStatus.PENDING
                                )
                                db.add(new_tweet)
                                db.commit()
                                st.success(f"Added to queue!")
                                time.sleep(0.5)
                                st.rerun()
                    with card_col4:
                        # Delete button (trash icon)
                        if st.button("🗑️", key=f"delete_trend_{trend.id}", help="Delete this trend"):
                            delete_trend(db, trend.id)
                            st.rerun()

                    # Details expander - FULL WIDTH (not in a column)
                    with st.expander("📋 View Details", expanded=False):
                        # Use columns inside expander for organized layout
                        detail_col1, detail_col2 = st.columns(2)
                        with detail_col1:
                            if trend.article_url and validate_safe_url(trend.article_url)[0]:
                                st.markdown(f"**🔗 Source:** [{html.escape(source_val)}]({html.escape(trend.article_url)})")
                            if trend.discovered_at:
                                st.markdown(f"**📅 Discovered:** {trend.discovered_at.strftime('%Y-%m-%d %H:%M')}")
                            if trend.keywords and isinstance(trend.keywords, list):
                                st.markdown(f"**🏷️ Keywords:** {', '.join(trend.keywords)}")
                        with detail_col2:
                            if trend.description:
                                st.markdown(f"**📝 Full Description:**")
                                st.markdown(html.escape(trend.description))
                            elif trend.summary:
                                st.markdown(f"**📝 Summary:**")
                                st.markdown(html.escape(trend.summary))

                    st.divider()
        else:
            st.info("No trends discovered yet. Go to Content to fetch trends.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Section 2: Processed Threads (Full Width) ---
    # Only show actual X/Twitter threads (not trend articles added to queue)
    all_tweets = db.query(Tweet).filter(
        Tweet.status.in_([TweetStatus.PROCESSED, TweetStatus.APPROVED, TweetStatus.PUBLISHED, TweetStatus.PENDING])
    ).order_by(Tweet.updated_at.desc()).limit(50).all()

    # Filter to only X/Twitter threads
    x_threads = [t for t in all_tweets if t.source_url and ('x.com/' in t.source_url or 'twitter.com/' in t.source_url)]
    threads_count = len(x_threads)

    # Collapsible section using checkbox styled as header
    threads_expanded = st.checkbox(
        f"🧵 Processed Threads ({threads_count})",
        value=st.session_state.home_threads_expanded,
        key="threads_section_toggle"
    )
    st.session_state.home_threads_expanded = threads_expanded

    if threads_expanded:
        if x_threads:
            for idx, tweet in enumerate(x_threads[:10]):  # Limit to 10
                status_str = tweet.status.value if hasattr(tweet.status, 'value') else str(tweet.status)

                # Preview: First 10-15 words of original text
                original_words = (tweet.original_text or '').split()
                preview_text = ' '.join(original_words[:15])
                if len(original_words) > 15:
                    preview_text += '...'
                preview_text = preview_text if preview_text else 'No content'

                # Source info - extract @username from X URL
                source_handle = ''
                if tweet.source_url:
                    try:
                        if 'x.com/' in tweet.source_url:
                            parts = tweet.source_url.split('x.com/')[1].split('/')
                            if parts:
                                source_handle = f"@{parts[0]}"
                        elif 'twitter.com/' in tweet.source_url:
                            parts = tweet.source_url.split('twitter.com/')[1].split('/')
                            if parts:
                                source_handle = f"@{parts[0]}"
                    except (IndexError, AttributeError):
                        pass

                with st.container():
                    # Preview row
                    preview_col1, preview_col2 = st.columns([5, 1])
                    with preview_col1:
                        st.markdown(f'**"{preview_text}"**')
                        status_source = f"Status: **{status_str}**"
                        if source_handle:
                            status_source += f" | Source: {source_handle}"
                        st.caption(status_source)
                    with preview_col2:
                        # SAFETY: status_str is from TweetStatus enum (controlled values)
                        st.markdown(f'<span class="status-badge status-{status_str.lower()}">{html.escape(status_str)}</span>', unsafe_allow_html=True)

                    # View Full Thread expander - FULL WIDTH
                    with st.expander("📖 View Full Thread"):
                        # Two-column layout inside expander for better readability
                        thread_col1, thread_col2 = st.columns(2)
                        with thread_col1:
                            st.markdown("**Original Thread:**")
                            st.text_area("", value=tweet.original_text or "No content", height=200, disabled=True, key=f"orig_{tweet.id}", label_visibility="collapsed")
                        with thread_col2:
                            st.markdown("**Hebrew Translation:**")
                            if tweet.hebrew_draft:
                                st.text_area("", value=tweet.hebrew_draft, height=200, disabled=True, key=f"heb_{tweet.id}", label_visibility="collapsed")
                            else:
                                st.info("No Hebrew translation yet.")

                        # Action buttons
                        btn1, btn2, btn3, btn4 = st.columns(4)
                        with btn1:
                            if tweet.source_url and tweet.source_url.startswith('http'):
                                st.markdown(f'[🔗 View Source]({tweet.source_url})')
                        with btn2:
                            if st.button("✏️ Edit", key=f"home_edit_{tweet.id}"):
                                st.session_state.selected_item = tweet.id
                                st.session_state.current_view = 'content'
                                st.rerun()

                    st.divider()
        else:
            st.info("No X/Twitter threads yet. Go to Content > Thread Translation to fetch and translate threads.")
