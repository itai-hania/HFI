DARK_MODE_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Dark Mode Design Tokens - Typefully Style */
    :root {
        --bg-primary: #020617;
        --bg-secondary: #0F172A;
        --bg-tertiary: #1E293B;
        --bg-elevated: #334155;

        --text-primary: #FFFFFF;
        --text-secondary: #CBD5E1;
        --text-muted: #94A3B8;

        --accent-primary: #22C55E;
        --accent-primary-hover: #16A34A;
        --accent-secondary: #3B82F6;
        --accent-success: #22C55E;
        --accent-warning: #F59E0B;
        --accent-danger: #EF4444;

        --border-default: rgba(255,255,255,0.08);
        --border-muted: rgba(255,255,255,0.04);

        --shadow-sm: 0 2px 8px rgba(0,0,0,0.25);
        --shadow-md: 0 4px 16px rgba(0,0,0,0.35);
        --shadow-lg: 0 12px 48px rgba(0,0,0,0.5);

        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 20px;
        --radius-pill: 9999px;
    }

    /* Base Dark Background */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    .main,
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        background: var(--bg-primary) !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: var(--text-primary) !important;
    }

    .main .block-container, [data-testid="stMainBlockContainer"] {
        padding: 1.5rem 2rem !important;
        max-width: 1400px !important;
    }

    /* Hide Streamlit elements */
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Typography - Light text on dark */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
        letter-spacing: -0.025em !important;
    }

    h1, .stMarkdown h1 { font-size: 1.75rem !important; margin-bottom: 0.5rem !important; }
    h2, .stMarkdown h2 { font-size: 1.25rem !important; }
    h3, .stMarkdown h3 { font-size: 1rem !important; color: var(--text-secondary) !important; }

    p, span, label, .stMarkdown, .stMarkdown p {
        font-family: 'Inter', sans-serif !important;
        color: var(--text-secondary) !important;
        font-size: 0.875rem !important;
        line-height: 1.6 !important;
    }

    /* ===========================================
       GRADIENT SIDEBAR - Typefully Style
       =========================================== */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F1318 0%, var(--bg-primary) 100%) !important;
        border-right: 1px solid var(--border-default) !important;
        width: 260px !important;
        min-width: 260px !important;
    }

    [data-testid="stSidebar"] .block-container {
        padding: 1rem 0.75rem !important;
        background: transparent !important;
    }

    /* Nav Brand with Gradient */
    .nav-brand {
        padding: 1.25rem 1.5rem 1.75rem 1.5rem;
        border-bottom: 1px solid var(--border-default);
        margin-bottom: 1rem;
        text-align: center;
    }

    .nav-brand h1 {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        background: linear-gradient(135deg, #FFFFFF 0%, var(--accent-secondary) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .nav-brand p {
        color: var(--text-muted) !important;
        font-size: 0.75rem !important;
        margin: 0.35rem 0 0 0 !important;
    }

    /* Sidebar Nav Buttons - Transparent with Active Indicator */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        color: var(--text-secondary) !important;
        border: none !important;
        font-weight: 500 !important;
        border-radius: 0 var(--radius-md) var(--radius-md) 0 !important;
        transition: all 0.2s ease !important;
        padding: 0.75rem 1rem !important;
    }

    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.05) !important;
        color: var(--text-primary) !important;
    }

    [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
        background: rgba(34, 197, 94, 0.15) !important;
        color: var(--accent-primary) !important;
        border-left: 3px solid var(--accent-primary) !important;
        font-weight: 600 !important;
    }

    [data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"]:hover {
        background: rgba(34, 197, 94, 0.22) !important;
    }

    [data-testid="stSidebar"] .stTextInput input {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border-default) !important;
        color: var(--text-primary) !important;
        border-radius: var(--radius-md) !important;
        font-size: 0.875rem !important;
    }

    [data-testid="stSidebar"] .stTextInput input::placeholder {
        color: var(--text-muted) !important;
    }

    [data-testid="stSidebar"] .stTextInput input:focus {
        border-color: var(--accent-secondary) !important;
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.18) !important;
    }

    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: var(--text-secondary) !important;
    }

    [data-testid="stSidebar"] hr {
        border-color: var(--border-default) !important;
        margin: 1rem 0 !important;
    }

    /* Nav Section Label */
    .nav-section {
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        padding: 1rem 1rem 0.5rem 1rem;
        margin-top: 0.5rem;
    }

    /* ===========================================
       CONTENT CARDS - Typefully Style
       =========================================== */
    .content-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        padding: 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid var(--border-default);
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }

    .content-card:hover {
        border-color: rgba(59, 130, 246, 0.35);
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
    }

    /* Stat Cards */
    .stat-card {
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        padding: 1.5rem 1.25rem;
        border: 1px solid var(--border-default);
        text-align: center;
        position: relative;
        overflow: hidden;
        transition: all 0.2s ease;
    }

    .stat-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--accent-primary);
        opacity: 0;
        transition: opacity 0.2s ease;
    }

    .stat-card:hover::before {
        opacity: 1;
    }

    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }

    .stat-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
    }

    .stat-label {
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 0.5rem;
    }

    .stat-inbox .stat-value { color: var(--accent-warning); }
    .stat-inbox::before { background: var(--accent-warning); }
    .stat-drafts .stat-value { color: var(--accent-primary); }
    .stat-drafts::before { background: var(--accent-primary); }
    .stat-ready .stat-value { color: var(--accent-success); }
    .stat-ready::before { background: var(--accent-success); }
    .stat-published .stat-value { color: var(--text-secondary); }
    .stat-published::before { background: var(--text-secondary); }

    /* ===========================================
       PILL BUTTONS - Typefully Style
       =========================================== */
    .stButton > button {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        padding: 0.625rem 1.25rem !important;
        border-radius: var(--radius-pill) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        box-shadow: var(--shadow-sm) !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover {
        background: var(--bg-elevated) !important;
        border-color: rgba(59, 130, 246, 0.35) !important;
        transform: translateY(-1px) !important;
        box-shadow: var(--shadow-md) !important;
    }

    .stButton > button[data-testid="baseButton-primary"] {
        background: rgba(34, 197, 94, 0.18) !important;
        color: #4ADE80 !important;
        border: 1px solid rgba(34, 197, 94, 0.4) !important;
        font-weight: 600 !important;
    }

    .stButton > button[data-testid="baseButton-primary"]:hover {
        background: rgba(34, 197, 94, 0.28) !important;
        box-shadow: none !important;
        transform: none !important;
    }

    /* Status Badges - Typefully Style with Borders */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        padding: 0.35rem 0.875rem;
        border-radius: var(--radius-pill);
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .status-pending {
        background: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .status-processed {
        background: rgba(59, 130, 246, 0.15);
        color: #60A5FA;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    .status-approved {
        background: rgba(34, 197, 94, 0.15);
        color: #4ADE80;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    .status-published {
        background: rgba(155, 163, 174, 0.15);
        color: #9BA3AE;
        border: 1px solid rgba(155, 163, 174, 0.3);
    }
    .status-failed {
        background: rgba(239, 68, 68, 0.15);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    /* Source Badges */
    .source-yahoo-finance { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .source-wsj { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .source-techcrunch { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .source-bloomberg { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .source-marketwatch { background: rgba(255, 193, 7, 0.15); color: #FFC107; border: 1px solid rgba(255, 193, 7, 0.3); }
    .source-manual { background: rgba(155, 163, 174, 0.15); color: #9BA3AE; border: 1px solid rgba(155, 163, 174, 0.3); }
    .source-x { background: rgba(255, 255, 255, 0.1); color: #E4E6EA; border: 1px solid rgba(255, 255, 255, 0.2); }

    /* Category Badges */
    .category-finance { background: rgba(255, 159, 10, 0.15); color: #FFA726; border: 1px solid rgba(255, 159, 10, 0.3); }
    .category-tech { background: rgba(33, 150, 243, 0.15); color: #42A5F5; border: 1px solid rgba(33, 150, 243, 0.3); }

    /* ===========================================
       FORM ELEMENTS - Typefully Style
       =========================================== */
    .stTextInput input, .stTextArea textarea {
        font-family: 'Inter', sans-serif !important;
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        font-size: 0.875rem !important;
        padding: 0.75rem 1rem !important;
        transition: all 0.2s ease !important;
    }

    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: var(--accent-secondary) !important;
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.18) !important;
        background: var(--bg-elevated) !important;
    }

    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: var(--text-muted) !important;
    }

    .stSelectbox > div > div {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-default) !important;
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        transition: all 0.2s ease !important;
    }

    .stSelectbox > div > div:hover {
        border-color: rgba(59, 130, 246, 0.35) !important;
    }

    .stCheckbox > label {
        font-size: 0.875rem !important;
        color: var(--text-secondary) !important;
    }

    /* Checkbox - Green when checked with white checkmark */
    /* Streamlit uses label[data-baseweb="checkbox"] > span for the visual checkbox */
    /* The span gets a background-image SVG checkmark when checked */
    label[data-baseweb="checkbox"] > span {
        transition: all 0.15s ease !important;
    }

    /* When checkbox input is checked (has aria-checked=true), style the preceding span */
    /* Since CSS can't select previous siblings, we use the label's state */
    label[data-baseweb="checkbox"]:has(input[aria-checked="true"]) > span {
        background-color: #22C55E !important;
        border-color: #22C55E !important;
        background-image: url("data:image/svg+xml,%3Csvg width='17' height='13' viewBox='0 0 17 13' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M6.50002 12.6L0.400024 6.60002L2.60002 4.40002L6.50002 8.40002L13.9 0.900024L16.1 3.10002L6.50002 12.6Z' fill='white'/%3E%3C/svg%3E") !important;
    }

    /* Unchecked state - dark background with subtle border */
    label[data-baseweb="checkbox"]:has(input[aria-checked="false"]) > span {
        background-color: var(--bg-tertiary) !important;
        border-color: var(--border-default) !important;
    }

    /* ===========================================
       PAGE HEADER - Typefully Style
       =========================================== */
    .page-header {
        margin-bottom: 2rem;
        padding-bottom: 1.25rem;
        border-bottom: 1px solid var(--border-default);
    }

    .page-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.025em;
        margin: 0 0 0.5rem 0;
    }

    .page-subtitle {
        font-size: 0.9rem;
        font-weight: 400;
        color: var(--text-muted);
        margin: 0;
    }

    /* ===========================================
       EMPTY STATE - Typefully Style
       =========================================== */
    .empty-state {
        text-align: center;
        padding: 4rem 2rem;
        background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
        border-radius: var(--radius-lg);
        border: 1px solid var(--border-default);
    }

    .empty-state-icon {
        font-size: 4rem;
        margin-bottom: 1.5rem;
        opacity: 0.3;
    }

    .empty-state-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.75rem;
    }

    .empty-state-text {
        color: var(--text-muted);
        font-size: 0.9rem;
        max-width: 400px;
        margin: 0 auto;
    }

    /* ===========================================
       PIPELINE COLUMNS
       =========================================== */
    .pipeline-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        background: var(--bg-tertiary);
        border-radius: var(--radius-md);
        margin-bottom: 0.75rem;
    }

    .pipeline-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text-primary);
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    .pipeline-count {
        background: var(--bg-elevated);
        padding: 0.15rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.7rem;
        font-weight: 600;
        color: var(--text-secondary);
    }

    /* Queue Item - Typefully Style with Slide Animation */
    .queue-item {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 1rem 1.25rem;
        margin-bottom: 0.75rem;
        border: 1px solid var(--border-default);
        transition: all 0.2s ease;
        cursor: pointer;
    }

    .queue-item:hover {
        border-color: rgba(59, 130, 246, 0.4);
        background: var(--bg-tertiary);
        box-shadow: var(--shadow-sm);
        transform: translateX(4px);
    }

    .queue-item-author {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 0.35rem;
    }

    .queue-item-text {
        font-size: 0.85rem;
        color: var(--text-secondary);
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    .queue-item-meta {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-top: 0.75rem;
        font-size: 0.7rem;
        color: var(--text-muted);
    }

    /* ===========================================
       EXPANDER (Dark)
       =========================================== */
    .streamlit-expanderHeader {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-default) !important;
        border-radius: var(--radius-md) !important;
        font-weight: 500 !important;
        color: var(--text-primary) !important;
    }

    .streamlit-expanderContent {
        border: 1px solid var(--border-default) !important;
        border-top: none !important;
        border-radius: 0 0 var(--radius-md) var(--radius-md) !important;
        background: var(--bg-secondary) !important;
    }

    details summary {
        color: var(--text-primary) !important;
    }

    /* ===========================================
       SCROLLBAR (Dark)
       =========================================== */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: var(--bg-primary);
    }

    ::-webkit-scrollbar-thumb {
        background: var(--bg-elevated);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
    }

    /* ===========================================
       ALERTS (Dark)
       =========================================== */
    [data-testid="stAlert"] {
        border-radius: var(--radius-md) !important;
        border: none !important;
        background: var(--bg-tertiary) !important;
    }

    /* ===========================================
       METRICS (Dark)
       =========================================== */
    [data-testid="stMetric"] {
        background: var(--bg-secondary) !important;
        padding: 1rem !important;
        border-radius: var(--radius-lg) !important;
        border: 1px solid var(--border-default) !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: var(--text-primary) !important;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: var(--text-muted) !important;
    }

    /* ===========================================
       TABS (Dark)
       =========================================== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: var(--text-secondary);
        border-radius: var(--radius-sm);
        padding: 0.5rem 1rem;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: var(--bg-tertiary);
        color: var(--text-primary);
    }

    .stTabs [aria-selected="true"] {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }

    /* ===========================================
       RESPONSIVE FOUNDATION
       =========================================== */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        overflow-x: hidden !important;
    }

    /* Tablet */
    @media (max-width: 1024px) {
        .main .block-container,
        [data-testid="stMainBlockContainer"] {
            max-width: 100% !important;
            padding: 1rem 1.25rem !important;
        }

        [data-testid="stSidebar"],
        [data-testid="stSidebar"] > div,
        [data-testid="stSidebarContent"],
        section[data-testid="stSidebar"] {
            width: 230px !important;
            min-width: 230px !important;
        }

        .page-title {
            font-size: 1.55rem !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
        }
    }

    /* Mobile */
    @media (max-width: 768px) {
        .main .block-container,
        [data-testid="stMainBlockContainer"] {
            max-width: 100% !important;
            padding: 0.75rem 0.75rem 5rem !important;
        }

        [data-testid="stSidebar"],
        [data-testid="stSidebar"] > div,
        [data-testid="stSidebarContent"],
        section[data-testid="stSidebar"] {
            width: 86vw !important;
            min-width: 86vw !important;
            max-width: 320px !important;
        }

        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.5rem !important;
        }

        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            min-width: 100% !important;
            flex: 1 1 100% !important;
            width: 100% !important;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"] {
            min-height: 44px !important;
        }

        [data-testid="stMetric"] {
            padding: 0.85rem !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.35rem !important;
        }

        .page-header {
            margin-bottom: 1.2rem !important;
            padding-bottom: 0.8rem !important;
        }

        .page-title {
            font-size: 1.35rem !important;
        }

        .page-subtitle {
            font-size: 0.8rem !important;
        }

        p, span, label, .stMarkdown, .stMarkdown p {
            font-size: 1rem !important;
            line-height: 1.55 !important;
        }

        .content-card,
        .stat-card,
        .translation-panel,
        .thread-tweet-item,
        .queue-item {
            padding: 0.9rem !important;
        }

        .stat-value {
            font-size: 2rem !important;
        }

        .status-badge {
            font-size: 0.6rem !important;
            padding: 0.3rem 0.65rem !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            overflow-y: hidden !important;
            white-space: nowrap !important;
            flex-wrap: nowrap !important;
            gap: 0.25rem !important;
            -webkit-overflow-scrolling: touch !important;
        }

        .stTabs [data-baseweb="tab"] {
            flex: 0 0 auto !important;
            white-space: nowrap !important;
            min-height: 44px !important;
            padding: 0.4rem 0.75rem !important;
        }

        /* Hover effects are less meaningful on touch screens */
        .content-card:hover,
        .stat-card:hover,
        .queue-item:hover {
            transform: none !important;
        }
    }

    /* Compact phones */
    @media (max-width: 480px) {
        .main .block-container,
        [data-testid="stMainBlockContainer"] {
            padding: 0.65rem 0.5rem 4.5rem !important;
        }

        h1, .stMarkdown h1, .page-title {
            font-size: 1.2rem !important;
        }

        h2, .stMarkdown h2 {
            font-size: 1.05rem !important;
        }

        p, span, label, .stMarkdown, .stMarkdown p {
            font-size: 1rem !important;
            line-height: 1.55 !important;
        }

        .nav-brand {
            padding: 0.9rem 0.85rem 1rem 0.85rem !important;
        }

        .nav-brand h1 {
            font-size: 1.25rem !important;
        }

        .translation-content {
            font-size: 1rem !important;
            line-height: 1.55 !important;
            padding: 0.65rem !important;
        }

        .thread-tweet-number {
            width: 1.25rem !important;
            height: 1.25rem !important;
            font-size: 0.62rem !important;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation: none !important;
            transition: none !important;
            scroll-behavior: auto !important;
        }
    }

    /* ===========================================
       SLIDER (Dark)
       =========================================== */
    .stSlider > div > div > div {
        background: var(--bg-elevated) !important;
    }

    .stSlider > div > div > div > div {
        background: var(--accent-primary) !important;
    }

    /* ===========================================
       PROGRESS BAR (Dark)
       =========================================== */
    .stProgress > div > div > div {
        background: var(--bg-elevated) !important;
    }

    .stProgress > div > div > div > div {
        background: var(--accent-primary) !important;
    }

    /* ===========================================
       DOWNLOAD BUTTON (Dark)
       =========================================== */
    .stDownloadButton > button {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-default) !important;
    }

    .stDownloadButton > button:hover {
        background: var(--bg-elevated) !important;
        border-color: var(--accent-primary) !important;
    }

    /* ===========================================
       MICRO-ANIMATIONS - Typefully Style
       =========================================== */
    * {
        transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }

    :focus-visible {
        outline: 2px solid var(--accent-secondary);
        outline-offset: 2px;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.35) !important;
    }

    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }

    .loading-shimmer {
        background: linear-gradient(90deg, var(--bg-secondary) 0%, var(--bg-tertiary) 50%, var(--bg-secondary) 100%);
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .fade-in {
        animation: fadeIn 0.3s ease-out;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    .pulse {
        animation: pulse 2s ease-in-out infinite;
    }

    /* ===========================================
       RTL SUPPORT FOR HEBREW CONTENT
       =========================================== */
    .rtl-container {
        direction: rtl;
        text-align: right;
        font-family: 'Heebo', 'Segoe UI', 'Arial', sans-serif;
    }

    .ltr-container {
        direction: ltr;
        text-align: left;
    }

    /* Side-by-side translation panel */
    .translation-panel {
        background: var(--bg-secondary);
        border-radius: var(--radius-lg);
        border: 1px solid var(--border-default);
        padding: 1.25rem;
        margin-bottom: 1rem;
    }

    .translation-panel-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        border-radius: var(--radius-sm);
        margin-bottom: 0.75rem;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .translation-panel-english {
        background: var(--bg-tertiary);
        color: var(--text-muted);
    }

    .translation-panel-hebrew {
        background: rgba(34, 197, 94, 0.1);
        color: var(--accent-success);
    }

    .translation-content {
        font-size: 0.9rem;
        line-height: 1.7;
        color: var(--text-secondary);
        padding: 0.75rem;
        background: var(--bg-tertiary);
        border-radius: var(--radius-sm);
        min-height: 60px;
        white-space: pre-wrap;
    }

    .translation-content.hebrew {
        direction: rtl;
        text-align: right;
        color: var(--text-primary);
        font-family: 'Heebo', 'David', 'Segoe UI', sans-serif;
    }

    .thread-tweet-item {
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        padding: 1rem;
        margin-bottom: 0.75rem;
        border: 1px solid var(--border-default);
        transition: all 0.2s ease;
    }

    .thread-tweet-item:hover {
        border-color: rgba(59, 130, 246, 0.35);
    }

    .thread-tweet-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.5rem;
        height: 1.5rem;
        background: var(--accent-secondary);
        color: white;
        font-size: 0.7rem;
        font-weight: 700;
        border-radius: 50%;
        margin-right: 0.5rem;
    }

    .thread-tweet-number.rtl {
        margin-right: 0;
        margin-left: 0.5rem;
    }

    /* Hebrew font loading */
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;600;700&display=swap');

    /* ===========================================
       RESPONSIVE BREAKPOINTS
       =========================================== */
    @media (max-width: 1200px) {
        .main .block-container, [data-testid="stMainBlockContainer"] {
            padding: 1.25rem 1.25rem !important;
        }
    }

    @media (max-width: 992px) {
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] > div,
        [data-testid="stSidebarContent"],
        section[data-testid="stSidebar"] {
            width: 220px !important;
            min-width: 220px !important;
        }

        .main .block-container, [data-testid="stMainBlockContainer"] {
            padding: 1rem !important;
        }
    }

    @media (max-width: 768px) {
        h1, .stMarkdown h1, .page-title {
            font-size: 1.4rem !important;
        }

        .main .block-container, [data-testid="stMainBlockContainer"] {
            padding: 0.75rem !important;
        }

        .empty-state {
            padding: 2rem 1rem;
        }
    }

    /* ===========================================
       REDUCED MOTION
       =========================================== */
    @media (prefers-reduced-motion: reduce) {
        * {
            animation: none !important;
            transition: none !important;
            scroll-behavior: auto !important;
        }

        .content-card:hover,
        .stat-card:hover,
        .queue-item:hover {
            transform: none !important;
        }
    }
</style>
"""
