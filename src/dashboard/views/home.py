import html

import streamlit as st
from sqlalchemy import or_

from common.models import Trend, Tweet, TweetStatus
from dashboard.db_helpers import delete_trend, get_stats
from dashboard.helpers import get_source_badge_class, safe_css_class
from dashboard.state import (
    KEY_HOME_PUBLISH_EXPANDED,
    KEY_HOME_THREADS_EXPANDED,
    KEY_HOME_TRENDS_EXPANDED,
    set_content_tab,
    set_current_view,
    set_selected_item,
    push_flash,
    rerun_view,
)
from dashboard.ui_components import render_page_header, render_section_header
from dashboard.ux_events import log_ux_event
from dashboard.validators import validate_safe_url


def render_home(db):
    """Home - overview of processed content and discovered trends."""
    render_page_header("Home", "Processed content, trend discovery, and publish handoff.")

    stats = get_stats(db)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="stat-card stat-inbox"><div class="stat-value">{stats["pending"]}</div><div class="stat-label">Inbox</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="stat-card stat-drafts"><div class="stat-value">{stats["processed"]}</div><div class="stat-label">Drafts</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="stat-card stat-ready"><div class="stat-value">{stats["ready_to_publish"]}</div><div class="stat-label">Ready</div></div>',
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f'<div class="stat-card stat-published"><div class="stat-value">{stats["published"]}</div><div class="stat-label">Published</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    _render_ready_to_publish(db)
    _render_discovered_trends(db)
    _render_processed_threads(db)


def _render_ready_to_publish(db):
    approved_tweets = (
        db.query(Tweet)
        .filter(Tweet.status == TweetStatus.APPROVED)
        .order_by(Tweet.updated_at.desc())
        .limit(10)
        .all()
    )
    if not approved_tweets:
        return

    expanded = st.checkbox(
        f"Ready to Publish ({len(approved_tweets)})",
        value=st.session_state.get(KEY_HOME_PUBLISH_EXPANDED, True),
        key="publish_section_toggle",
    )
    st.session_state[KEY_HOME_PUBLISH_EXPANDED] = expanded

    if not expanded:
        st.markdown("<br>", unsafe_allow_html=True)
        return

    render_section_header("Approved Queue", "Review approved items before scheduling or manual publishing.")

    for tweet in approved_tweets:
        preview = html.escape((tweet.hebrew_draft or "")[:80])
        if len(tweet.hebrew_draft or "") > 80:
            preview += "..."
        trend_title = html.escape(tweet.trend_topic or "Unknown")
        updated = tweet.updated_at.strftime("%Y-%m-%d %H:%M") if tweet.updated_at else ""

        with st.container():
            col_content, col_actions = st.columns([6, 1])
            with col_content:
                st.markdown(
                    f"""
                    <div style="padding: 0.4rem 0;">
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span style="font-size: 0.8rem; font-weight: 500; color: var(--text-primary);">{trend_title}</span>
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); direction: rtl; text-align: right; margin-top: 0.25rem;">{preview}</div>
                        <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 0.15rem;">Approved {updated}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col_actions:
                if st.button("Edit", key=f"pub_edit_{tweet.id}", use_container_width=True):
                    set_selected_item(tweet.id)
                    set_current_view("content")
                    set_content_tab("Queue")
                    log_ux_event("open_editor_from_ready_queue", "home", success=True)
                    rerun_view()
        st.markdown("<hr style='margin: 0.25rem 0; border-color: var(--border-default);'>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)


def _render_discovered_trends(db):
    trends = db.query(Trend).order_by(Trend.discovered_at.desc()).limit(15).all()
    trends_count = len(trends)

    trend_titles = [t.title for t in trends if t.title]
    if trend_titles:
        queued_titles = {
            row[0]
            for row in db.query(Tweet.trend_topic).filter(
                Tweet.trend_topic.isnot(None),
                Tweet.trend_topic.in_(trend_titles),
            ).all()
        }
    else:
        queued_titles = set()

    expanded = st.checkbox(
        f"Discovered Trends ({trends_count})",
        value=st.session_state.get(KEY_HOME_TRENDS_EXPANDED, True),
        key="trends_section_toggle",
    )
    st.session_state[KEY_HOME_TRENDS_EXPANDED] = expanded

    if not expanded:
        st.markdown("<br>", unsafe_allow_html=True)
        return

    render_section_header("Discovered Trends", "Review, generate, and queue candidate trends.")

    if not trends:
        st.info("No trends discovered yet. Use Content > Acquire to fetch trends.")
        st.markdown("<br>", unsafe_allow_html=True)
        return

    for idx, trend in enumerate(trends):
        source_val = trend.source.value if hasattr(trend.source, "value") else str(trend.source)
        badge_cls = get_source_badge_class(source_val)
        safe_title = html.escape(trend.title or "")
        in_queue = trend.title in queued_titles

        summary_text = ""
        if trend.summary:
            summary_text = html.escape(trend.summary[:250]) + ("..." if len(trend.summary) > 250 else "")
        elif trend.description and len(trend.description) > 10:
            summary_text = html.escape(trend.description[:200]) + "..."

        with st.container():
            col_content, col_meta, col_actions = st.columns([6, 2, 2])
            with col_content:
                if trend.article_url and validate_safe_url(trend.article_url)[0]:
                    st.markdown(f"**#{idx + 1}** [{safe_title}]({html.escape(trend.article_url)})")
                else:
                    st.markdown(f"**#{idx + 1}** {safe_title}")

                if summary_text:
                    st.caption(summary_text)

                if trend.keywords and isinstance(trend.keywords, list):
                    safe_keywords = ", ".join([html.escape(str(kw)) for kw in trend.keywords[:5]])
                    st.caption(f"Keywords: {safe_keywords}")

            with col_meta:
                st.markdown(f'<span class="status-badge {badge_cls}">{html.escape(source_val)}</span>', unsafe_allow_html=True)
                if trend.source_count and trend.source_count > 1:
                    st.caption(f"{trend.source_count} sources")

            with col_actions:
                action_col1, action_col2 = st.columns(2)
                with action_col1:
                    if st.button("Generate", key=f"home_gen_{trend.id}", use_container_width=True):
                        source = f"{trend.title}\n\n{trend.description or trend.summary or ''}"
                        st.session_state["generate_source_text"] = source.strip()
                        set_current_view("content")
                        set_content_tab("Generate")
                        log_ux_event("generate_from_trend_card", "home", success=True)
                        rerun_view()
                with action_col2:
                    if st.button("Delete trend", key=f"delete_trend_{trend.id}", use_container_width=True):
                        delete_trend(db, trend.id)
                        push_flash("warning", "Trend removed from discovery list.", view="home")
                        log_ux_event("delete_trend", "home", success=True, metadata={"trend_id": trend.id})
                        rerun_view()

                if in_queue:
                    st.caption("Already in queue")
                else:
                    if st.button("Add to Queue", key=f"home_add_trend_{trend.id}", use_container_width=True):
                        new_tweet = Tweet(
                            source_url=trend.article_url or f"trend_{trend.id}",
                            original_text=f"{trend.title}\n\n{trend.description or trend.summary or ''}",
                            trend_topic=trend.title,
                            status=TweetStatus.PENDING,
                        )
                        db.add(new_tweet)
                        db.commit()
                        push_flash("success", "Trend added to queue.", view="home")
                        log_ux_event("add_trend_to_queue", "home", success=True, metadata={"trend_id": trend.id})
                        rerun_view()

            with st.expander("View details", expanded=False):
                dcol1, dcol2 = st.columns(2)
                with dcol1:
                    if trend.article_url and validate_safe_url(trend.article_url)[0]:
                        st.markdown(f"**Source:** [{html.escape(source_val)}]({html.escape(trend.article_url)})")
                    if trend.discovered_at:
                        st.markdown(f"**Discovered:** {trend.discovered_at.strftime('%Y-%m-%d %H:%M')}")
                    if trend.keywords and isinstance(trend.keywords, list):
                        safe_keywords = ", ".join([html.escape(str(kw)) for kw in trend.keywords])
                        st.markdown(f"**Keywords:** {safe_keywords}")
                with dcol2:
                    if trend.description:
                        st.markdown("**Description:**")
                        st.markdown(html.escape(trend.description))
                    elif trend.summary:
                        st.markdown("**Summary:**")
                        st.markdown(html.escape(trend.summary))
        st.divider()

    st.markdown("<br>", unsafe_allow_html=True)


def _render_processed_threads(db):
    x_threads = (
        db.query(Tweet)
        .filter(
            Tweet.status.in_(
                [
                    TweetStatus.PROCESSED,
                    TweetStatus.APPROVED,
                    TweetStatus.PUBLISHED,
                    TweetStatus.PENDING,
                ]
            ),
            or_(Tweet.source_domain == "x.com", Tweet.source_domain == "twitter.com"),
        )
        .order_by(Tweet.updated_at.desc())
        .limit(10)
        .all()
    )
    threads_count = len(x_threads)

    expanded = st.checkbox(
        f"Processed Threads ({threads_count})",
        value=st.session_state.get(KEY_HOME_THREADS_EXPANDED, True),
        key="threads_section_toggle",
    )
    st.session_state[KEY_HOME_THREADS_EXPANDED] = expanded

    if not expanded:
        return

    render_section_header("Processed Threads", "Open full thread content and route back to editor when needed.")

    if not x_threads:
        st.info("No X/Twitter threads yet. Use Content > Thread Translation to fetch and translate threads.")
        return

    for tweet in x_threads:
        status_str = tweet.status.value if hasattr(tweet.status, "value") else str(tweet.status)

        words = (tweet.original_text or "").split()
        preview_text = " ".join(words[:15]) if words else "No content"
        if len(words) > 15:
            preview_text += "..."

        source_handle = ""
        if tweet.source_url:
            try:
                if "x.com/" in tweet.source_url:
                    source_handle = f"@{tweet.source_url.split('x.com/')[1].split('/')[0]}"
                elif "twitter.com/" in tweet.source_url:
                    source_handle = f"@{tweet.source_url.split('twitter.com/')[1].split('/')[0]}"
            except (IndexError, AttributeError):
                source_handle = ""

        with st.container():
            pcol1, pcol2 = st.columns([5, 1])
            with pcol1:
                st.markdown(f'**"{html.escape(preview_text)}"**')
                status_line = f"Status: **{status_str}**"
                if source_handle:
                    status_line += f" | Source: {source_handle}"
                st.caption(status_line)
            with pcol2:
                st.markdown(
                    f'<span class="status-badge status-{safe_css_class(status_str.lower())}">{html.escape(status_str)}</span>',
                    unsafe_allow_html=True,
                )

            with st.expander("View full thread"):
                tcol1, tcol2 = st.columns(2)
                with tcol1:
                    st.markdown("**Original thread**")
                    st.text_area(
                        "Original thread content",
                        value=tweet.original_text or "No content",
                        height=200,
                        disabled=True,
                        key=f"orig_{tweet.id}",
                    )
                with tcol2:
                    st.markdown("**Hebrew translation**")
                    if tweet.hebrew_draft:
                        st.text_area(
                            "Hebrew translation content",
                            value=tweet.hebrew_draft,
                            height=200,
                            disabled=True,
                            key=f"heb_{tweet.id}",
                        )
                    else:
                        st.info("No Hebrew translation yet.")

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if tweet.source_url and validate_safe_url(tweet.source_url)[0]:
                        st.markdown(f"[View source]({html.escape(tweet.source_url)})")
                with bcol2:
                    if st.button("Edit", key=f"home_edit_{tweet.id}", use_container_width=True):
                        set_selected_item(tweet.id)
                        set_current_view("content")
                        set_content_tab("Queue")
                        log_ux_event("open_editor_from_processed_threads", "home", success=True)
                        rerun_view()
        st.divider()
