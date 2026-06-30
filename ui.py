# ui.py
import streamlit as st
import asyncio
import json
import os
import time
from app.main import run_prototype

# 1. Page Configuration & Shell Layout
st.set_page_config(
    page_title="Web Scraping AI Agent", 
    page_icon="🤖", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize a clean visibility tracking state for our sidebar controls
if "sidebar_visible" not in st.session_state:
    st.session_state.sidebar_visible = True

# Initialize session state configuration parameters
if "session_persistence" not in st.session_state:
    st.session_state.session_persistence = True
if "cookie_bypass" not in st.session_state:
    st.session_state.cookie_bypass = True
if "enable_form" not in st.session_state:
    st.session_state.enable_form = False
if "form_actions_json" not in st.session_state:
    st.session_state.form_actions_json = '[\n  {"selector": "input.search", "action": "type", "value": "scraping"},\n  {"selector": "input.submit", "action": "click"}\n]'
if "enable_pagination" not in st.session_state:
    st.session_state.enable_pagination = False
if "next_page_selector" not in st.session_state:
    st.session_state.next_page_selector = "li.next > a"
if "max_pages" not in st.session_state:
    st.session_state.max_pages = 2
if "proxy_server" not in st.session_state:
    st.session_state.proxy_server = ""
if "network_throttling" not in st.session_state:
    st.session_state.network_throttling = "Fastest"

# 2. Advanced Premium CSS: Gemini-Inspired Dark Core & Glassmorphism
st.markdown("""
    <style>
        /* Gemini Central Aura Shifting/Breathing Animation */
        @keyframes geminiBreathing {
            0% { transform: translate(-50%, -50%) scale(1); opacity: 0.45; filter: blur(250px); }
            50% { transform: translate(-50%, -50%) scale(1.2); opacity: 0.60; filter: blur(320px); }
            100% { transform: translate(-50%, -50%) scale(1); opacity: 0.45; filter: blur(250px); }
        }

        /* Base Dark Canvas Shell */
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #050816 !important;
            background: radial-gradient(circle at 50% 0%, #0b1120 0%, #050816 100%) !important;
            color: #f8fafc !important;
            font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
            overflow-x: hidden;
        }

        /* Gemini Blurred Floating Radial Glow Background Element */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            top: 45%;
            left: 50%;
            width: 650px;
            height: 650px;
            background: radial-gradient(circle, rgba(37,99,235,0.22) 0%, rgba(67,56,202,0.18) 35%, rgba(6,182,212,0.12) 65%, transparent 100%);
            z-index: 0;
            pointer-events: none;
            transform: translate(-50%, -50%);
            animation: geminiBreathing 14s ease-in-out infinite;
        }

        /* Ensure main text layers sit securely on top of glows */
        [data-testid="stVerticalBlock"] {
            position: relative;
            z-index: 1;
        }

        /* Hide Default Streamlit Design Overlays */
        header, footer, #MainMenu { visibility: hidden !important; }

        /* Semi-Transparent Glassmorphism Sidebar */
        section[data-testid="stSidebar"] {
            background: rgba(5, 8, 22, 0.45) !important;
            backdrop-filter: blur(24px) saturate(150%) !important;
            -webkit-backdrop-filter: blur(24px) saturate(150%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
        }

        /* Dark Glass Input Field */
        div[data-testid="stTextInput"] input {
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 10px !important;
            color: #f8fafc !important;
            padding: 12px 16px !important;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
        }
        div[data-testid="stTextInput"] input:focus {
            border-color: rgba(6, 182, 212, 0.6) !important;
            box-shadow: 0 0 20px rgba(6, 182, 212, 0.25) !important;
            background: rgba(15, 23, 42, 0.8) !important;
        }

        /* Gradient Scraper Button (Blue -> Purple Hover Lift) */
        div.stButton > button:first-child {
            background: linear-gradient(90deg, #2563eb, #8b5cf6) !important;
            border: none !important;
            border-radius: 10px !important;
            color: #ffffff !important;
            padding: 14px 24px !important;
            font-weight: 600 !important;
            letter-spacing: 0.025em !important;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
            box-shadow: 0 4px 20px rgba(37, 99, 235, 0.2) !important;
        }
        div.stButton > button:first-child:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 25px rgba(139, 92, 246, 0.4) !important;
        }

        /* Premium Glassmorphic General Cards */
        .glass-card {
            background: rgba(17, 24, 39, 0.45) !important;
            backdrop-filter: blur(20px) saturate(140%) !important;
            -webkit-backdrop-filter: blur(20px) saturate(140%) !important;
            border: 1px solid rgba(255, 255, 255, 0.07) !important;
            border-radius: 16px !important;
            padding: 24px !important;
            margin-bottom: 24px !important;
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .glass-card:hover {
            border-color: rgba(6, 182, 212, 0.3) !important;
            box-shadow: 0 12px 40px rgba(6, 182, 212, 0.08) !important;
            transform: translateY(-2px);
        }

        /* Plain Wording Tab Overrides */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            background: transparent !important;
            color: #cbd5e1 !important;
            font-weight: 500 !important;
            padding: 10px 20px !important;
            border-radius: 8px !important;
            transition: all 0.2s ease !important;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(255, 255, 255, 0.06) !important;
            color: #06b6d4 !important;
            font-weight: 600 !important;
            box-shadow: inset 0 0 0 1px rgba(6, 182, 212, 0.2) !important;
        }

        /* VS-Code Inspired Code Panel Container */
        div[data-testid="stJson"] {
            background: #02040a !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 12px !important;
            padding: 18px !important;
        }
        div[data-testid="stJson"] span {
            color: #06b6d4 !important;
            font-family: 'Fira Code', 'Courier New', monospace !important;
        }

        /* Premium Browser Chrome mock container */
        .browser-frame {
            background: #0f172a;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        .browser-header-bar {
            background: #0b0f19;
            padding: 12px 16px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .dot-r { background: #ef4444; } .dot-y { background: #f59e0b; } .dot-g { background: #10b981; }
        .browser-address-field {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            padding: 4px 16px;
            font-size: 0.8rem;
            color: #94a3b8;
            margin-left: 16px;
            width: 40%;
        }

        /* Simple Timeline System Layout rules */
        .timeline-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 0;
            font-size: 0.95rem;
        }
        .status-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 2px 10px;
            border-radius: 9999px;
            color: #10b981;
            font-size: 0.75rem;
            font-weight: 600;
        }

        /* Force dark text overrides to ignore global white-outs */
        div[data-testid="stExpander"] h1, 
        div[data-testid="stExpander"] h2, 
        div[data-testid="stExpander"] p,
        div[data-testid="stExpander"] span {
            color: #ffffff !important;
        }

        /* High-contrast Logo Inversion for Dark Theme */
        .logo-image-container img {
            filter: invert(1) !important;
            background-color: transparent !important;
        }
    </style>
""", unsafe_allow_html=True)

# ─── MAIN HEADER DISPLAY LAYER ───
header_col, toggle_col = st.columns([4, 1])

with header_col:
    st.markdown("""
        <div style='margin-bottom: 20px; position: relative; z-index: 1;'>
            <div style='display: flex; align-items: center; gap: 12px; margin-bottom: 10px;'>
                <span class='status-pill'><span style='color: #10b981; font-size: 1.25rem;'>●</span> Agent Ready</span>
            </div>
            <h1 style='font-size: 2.8rem; font-weight: 800; background: linear-gradient(90deg, #f8fafc, #06b6d4, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;'>
                Web Scraping AI Agent
            </h1>
            <p style='color: #cbd5e1; font-size: 1.05rem; max-width: 600px; margin-top: 4px; margin-bottom: 0;'>
                Automatically reads website text layouts, downloads file assets, and structures clean database models.
                </p>
            </div>
    """, unsafe_allow_html=True)

with toggle_col:
    if st.session_state.sidebar_visible:
        if st.button("❌ Hide Controls", use_container_width=True):
            st.session_state.sidebar_visible = False
            st.rerun()
    else:
        if st.button("⚙️ Show Controls", type="primary", use_container_width=True):
            st.session_state.sidebar_visible = True
            st.rerun()

# ─── SIDEBAR RENDERING SYSTEM ───
url_input = "https://quotes.toscrape.com/js/"
trigger_btn = False

if st.session_state.sidebar_visible:
    with st.sidebar:
        st.markdown("<h2 style='color: white; font-size: 1.4rem; margin-bottom: 20px;'>🔮 Configuration</h2>", unsafe_allow_html=True)
        st.markdown("**Target Website Link:**")
        url_input = st.text_input("Enter URL Address Link:", value="https://quotes.toscrape.com/js/", label_visibility="collapsed")
        
        st.markdown("---")
        
        with st.expander("🔐 Session & Banners"):
            st.checkbox("Enable Session Persistence", key="session_persistence")
            st.checkbox("Cookie Banner Auto-Bypass", key="cookie_bypass")
        
        with st.expander("✍️ Form Orchestration"):
            st.checkbox("Enable Form Orchestration", key="enable_form")
            st.text_area("Form Actions (JSON Array):", key="form_actions_json", height=120)
            
        with st.expander("📄 Pagination"):
            st.checkbox("Enable Multi-Page Scraping", key="enable_pagination")
            st.text_input("Next Page Selector:", key="next_page_selector")
            st.number_input("Max Pages to Crawl:", min_value=1, max_value=10, key="max_pages", step=1)

        with st.expander("🌐 Network & Proxy"):
            st.text_input("Proxy Server (IP:Port or User:Pass@IP:Port):", key="proxy_server", placeholder="e.g. http://127.0.0.1:8000")
            st.selectbox("Network Emulation Throttling Preset:", ["Fastest", "Fast 3G", "Slow 3G"], key="network_throttling")
        
        st.markdown("---")
        st.markdown("**AI Core Subsystems Active**")
        st.markdown("""
            <div style='background: rgba(255,255,255,0.03); padding: 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05);'>
                <p style='margin: 0 0 8px 0; font-size: 0.85rem;'><span style='color: #06b6d4;'>⚡</span> Headless Browser Core</p>
                <p style='margin: 0 0 8px 0; font-size: 0.85rem;'><span style='color: #8b5cf6;'>🛡</span> Pydantic Strict Checkers</p>
                <p style='margin: 0; font-size: 0.85rem;'><span style='color: #2563eb;'>◈</span> Dynamic DOM Extraction</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        trigger_btn = st.button("Start AI Scraper", use_container_width=True)
        if st.button("🔄 Force Refresh Cache", use_container_width=True, key="sb_force_refresh"):
            st.cache_data.clear()
            if os.path.exists("prototype_output.json"):
                try: os.remove("prototype_output.json")
                except: pass
            if os.path.exists("storage/crawl_history.json"):
                try: os.remove("storage/crawl_history.json")
                except: pass
            if os.path.exists("storage/session_state.json"):
                try: os.remove("storage/session_state.json")
                except: pass
            st.toast("Telemetry, crawl history database, and output caches cleared!", icon="🔄")
            st.rerun()
else:
    st.markdown("---")
    sc_col1, sc_col2 = st.columns([3, 1])
    with sc_col1:
        url_input = st.text_input("Target URL Address:", value="https://quotes.toscrape.com/js/")
    with sc_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        trigger_btn = st.button("Start AI Scraper", type="primary", use_container_width=True)
        if st.button("🔄 Force Refresh Cache", use_container_width=True, key="main_force_refresh"):
            st.cache_data.clear()
            if os.path.exists("prototype_output.json"):
                try: os.remove("prototype_output.json")
                except: pass
            if os.path.exists("storage/crawl_history.json"):
                try: os.remove("storage/crawl_history.json")
                except: pass
            if os.path.exists("storage/session_state.json"):
                try: os.remove("storage/session_state.json")
                except: pass
            st.toast("Telemetry, crawl history database, and output caches cleared!", icon="🔄")
            st.rerun()

# ─── RUNNING PIPELINE MONITOR STAGES ───
if trigger_btn or os.path.exists("prototype_output.json"):
    # If button clicked, execute backend scraper runtime context
    if trigger_btn:
        if not url_input.strip():
            st.error("Please enter a valid website address link to begin.")
        else:
            timeline_box = st.empty()
            
            steps = [
                ("browser", "Launch Browser Core Engine"),
                ("dom", "Analyze DOM Object Tree Structs"),
                ("assets", "Download & Preserve Binary Media Assets"),
                ("json", "Generate Validated Database Packages")
            ]
            
            current_state = {k: {"icon": "⏳", "status": "Waiting..."} for k, _ in steps}
            
            def render_ui_timeline():
                html_stream = "<div class='glass-card'><h5>⏳ AI Workflow Progress Timeline</h5><div style='margin-top: 16px;'>"
                for key, name in steps:
                    info = current_state[key]
                    html_stream += f"""
                    <div class='timeline-item'>
                        <div style='font-size: 1.2rem; width: 24px;'>{info['icon']}</div>
                        <div style='flex-grow: 1; color: #f8fafc;'><b>{name}</b></div>
                        <div style='color: #64748b; font-size: 0.85rem;'>{info['status']}</div>
                    </div>
                    """
                html_stream += "</div></div>"
                timeline_box.markdown(html_stream, unsafe_allow_html=True)

            current_state["browser"] = {"icon": "⟳", "status": "Processing..."}
            render_ui_timeline()
            time.sleep(1.2)
            current_state["browser"] = {"icon": "✓", "status": "Complete"}
            
            current_state["dom"] = {"icon": "⟳", "status": "Processing..."}
            render_ui_timeline()
            time.sleep(1.0)
            current_state["dom"] = {"icon": "✓", "status": "Complete"}
            
            current_state["assets"] = {"icon": "⟳", "status": "Processing..."}
            current_state["json"] = {"icon": "⟳", "status": "Processing..."}
            render_ui_timeline()
            
            # Parse form orchestration actions
            form_actions = None
            if st.session_state.enable_form:
                try:
                    form_actions = json.loads(st.session_state.form_actions_json)
                    if not isinstance(form_actions, list):
                        st.error("Form Actions must be a valid JSON array.")
                        st.stop()
                except Exception as json_err:
                    st.error(f"Failed to parse Form Actions JSON: {str(json_err)}")
                    st.stop()
            
            # Pagination selector & max pages
            next_sel = st.session_state.next_page_selector if st.session_state.enable_pagination else None
            max_p = int(st.session_state.max_pages) if st.session_state.enable_pagination else 1
            
            try:
                asyncio.run(run_prototype(
                    url_input,
                    form_actions=form_actions,
                    next_page_selector=next_sel,
                    max_pages=max_p,
                    session_persistence=st.session_state.session_persistence,
                    cookie_bypass=st.session_state.cookie_bypass,
                    proxy_server=st.session_state.proxy_server,
                    network_throttling=st.session_state.network_throttling
                ))
                current_state["assets"] = {"icon": "✓", "status": "Complete"}
                current_state["json"] = {"icon": "✓", "status": "Complete"}
                render_ui_timeline()
                time.sleep(0.4)
                st.toast("Success! Extracted data checked and approved.", icon="✅")
            except Exception as e:
                st.error(f"Something went wrong inside the core code thread: {str(e)}")
                
            timeline_box.empty()

    json_path = "prototype_output.json"
    data_payload = {}
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            data_payload = json.load(f)

    # ─── ENTERPRISE-GRADE GLASSMORPHIC PERFORMANCE GRIDS ───
    status_txt = data_payload.get("status", "FAILED").upper()
    if status_txt == "FAILED":
        category = data_payload.get("failure_category", "generic_error").upper()
        reason = data_payload.get("failure_reason", "An unknown error occurred during execution.")
        
        st.markdown(f"""
            <div class='glass-card' style='border-color: rgba(239, 68, 68, 0.4) !important;'>
                <div style='display: flex; align-items: center; gap: 12px; margin-bottom: 12px;'>
                    <span style='background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 12px; border-radius: 9999px; color: #ef4444; font-size: 0.8rem; font-weight: 600;'>
                        ⚠️ SCRAPING FAILED
                    </span>
                    <span style='color: #ef4444; font-weight: 700; font-size: 1.1rem;'>Category: {category}</span>
                </div>
                <p style='color: #f1f5f9; font-size: 1rem; line-height: 1.6;'>{reason}</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Display logs and JSON output for troubleshooting
        layout_left, layout_right = st.columns([1, 1])
        with layout_left:
            st.markdown("##### 🔍 Scraper Execution Details & Metadata")
            st.json(data_payload.get("metadata", {}))
        with layout_right:
            st.markdown("##### 💎 Complete Fail Output JSON")
            st.json(data_payload)
            
    else:
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Scraper Status</div><div style='font-size: 1.8rem; font-weight: 700; color: #06b6d4; margin-top: 6px;'>{status_txt}</div></div>", unsafe_allow_html=True)
        with m2:
            val_grade = int(data_payload.get("quality_score", 0.0) * 100)
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Data Quality Grade</div><div style='font-size: 1.8rem; font-weight: 700; color: #10b981; margin-top: 6px;'>{val_grade}%</div></div>", unsafe_allow_html=True)
        with m3:
            lnks_len = len(data_payload.get("links", []))
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Found Web Links</div><div style='font-size: 1.8rem; font-weight: 700; color: #ffffff; margin-top: 6px;'>{lnks_len} Pages</div></div>", unsafe_allow_html=True)
        with m4:
            imgs_len = len(data_payload.get("images", []))
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Saved Images</div><div style='font-size: 1.8rem; font-weight: 700; color: #8b5cf6; margin-top: 6px;'>{imgs_len} Files</div></div>", unsafe_allow_html=True)
        with m5:
            sync_type = data_payload.get("metadata", {}).get("sync_type", "Full Sync")
            sync_color = "#10b981" if sync_type == "Incremental Delta Sync" else "#f59e0b"
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Sync Strategy</div><div style='font-size: 1.5rem; font-weight: 700; color: {sync_color}; margin-top: 6px;'>{sync_type}</div></div>", unsafe_allow_html=True)

        # ─── PERFORMANCE METRICS & SCORING ROW ───
        perf = data_payload.get("metadata", {}).get("performance", {})
        completeness = int(data_payload.get("metadata", {}).get("completeness_score", 0.0) * 100)
        confidence = int(data_payload.get("metadata", {}).get("confidence_score", 0.0) * 100)
        quality = int(data_payload.get("metadata", {}).get("quality_score", 0.0) * 100)
        
        p1, p2, p3, p4, p5 = st.columns(5)
        with p1:
            dom_time = perf.get("dom_ready_time_ms", 0.0)
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>DOM Ready Time</div><div style='font-size: 1.6rem; font-weight: 700; color: #06b6d4; margin-top: 6px;'>{dom_time} ms</div></div>", unsafe_allow_html=True)
        with p2:
            load_time = perf.get("load_duration_ms", 0.0)
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Load Duration</div><div style='font-size: 1.6rem; font-weight: 700; color: #06b6d4; margin-top: 6px;'>{load_time} ms</div></div>", unsafe_allow_html=True)
        with p3:
            payload_bytes = perf.get("total_payload_bytes", 0)
            payload_kb = round(payload_bytes / 1024, 2)
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Total Payload</div><div style='font-size: 1.6rem; font-weight: 700; color: #ffffff; margin-top: 6px;'>{payload_kb} KB</div></div>", unsafe_allow_html=True)
        with p4:
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Completeness / Confidence</div><div style='font-size: 1.6rem; font-weight: 700; color: #10b981; margin-top: 6px;'>{completeness}% / {confidence}%</div></div>", unsafe_allow_html=True)
        with p5:
            st.markdown(f"<div class='glass-card'><div style='color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>Data Quality Score</div><div style='font-size: 1.6rem; font-weight: 700; color: #8b5cf6; margin-top: 6px;'>{quality}%</div></div>", unsafe_allow_html=True)

        layout_left, layout_right = st.columns([1, 1.2], gap="large")

        with layout_left:
            st.markdown("<h4 style='font-size: 0.95rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; margin-bottom: 14px;'>📸 Website Visual Proof Frame</h4>", unsafe_allow_html=True)
            # Multi-viewport screenshot previews
            viewport_tabs = st.tabs(["🖥️ Desktop", "📱 Tablet", "📞 Mobile"])
            
            # Helper to read and render cache-busted images safely
            def render_cache_busted_image(path_with_query: str, **kwargs):
                # Clean path to check existence and read file
                clean_path = path_with_query.split("?")[0]
                if os.path.exists(clean_path):
                    try:
                        with open(clean_path, "rb") as f:
                            st.image(f.read(), **kwargs)
                        return True
                    except Exception as e:
                        st.error(f"Failed to read image for cache-busting: {str(e)}")
                return False

            # Generate dynamic query timestamp for cache busting
            timestamp = int(time.time())

            desktop_above_fold = f"{data_payload.get('desktop_above_fold') or 'storage/screenshots/desktop_above_fold.png'}?t={timestamp}"
            desktop_full = f"storage/screenshots/full_page.png?t={timestamp}"
            tablet_path = f"{data_payload.get('tablet_view') or 'storage/screenshots/tablet_view.png'}?t={timestamp}"
            mobile_path = f"{data_payload.get('mobile_view') or 'storage/screenshots/mobile_view.png'}?t={timestamp}"

            with viewport_tabs[0]:
                desktop_preview = st.radio("Desktop Snapshot Range:", ["Above the Fold", "Full Page"], horizontal=True, key="desktop_preview_select")
                path_to_show = desktop_above_fold if desktop_preview == "Above the Fold" else desktop_full
                
                clean_path_to_show = path_to_show.split("?")[0]
                if os.path.exists(clean_path_to_show):
                    st.markdown(f"""
                        <div class='browser-frame'>
                            <div class='browser-header-bar'>
                                <span class='dot dot-r'></span><span class='dot dot-y'></span><span class='dot dot-g'></span>
                                <div class='browser-address-field'>{data_payload.get('url', url_input)}</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    render_cache_busted_image(path_to_show, use_container_width=True)
                else:
                    st.warning("Desktop screenshot not found on disk.")
                    
            with viewport_tabs[1]:
                clean_tablet_path = tablet_path.split("?")[0]
                if os.path.exists(clean_tablet_path):
                    st.markdown(f"""
                        <div class='browser-frame' style='max-width: 480px; margin: auto;'>
                            <div class='browser-header-bar'>
                                <span class='dot dot-r'></span><span class='dot dot-y'></span><span class='dot dot-g'></span>
                                <div class='browser-address-field'>{data_payload.get('url', url_input)}</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    render_cache_busted_image(tablet_path, width=480)
                else:
                    st.warning("Tablet screenshot not found on disk.")
                    
            with viewport_tabs[2]:
                clean_mobile_path = mobile_path.split("?")[0]
                if os.path.exists(clean_mobile_path):
                    st.markdown(f"""
                        <div class='browser-frame' style='max-width: 320px; margin: auto;'>
                            <div class='browser-header-bar'>
                                <span class='dot dot-r'></span><span class='dot dot-y'></span><span class='dot dot-g'></span>
                                <div class='browser-address-field'>{data_payload.get('url', url_input)}</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    render_cache_busted_image(mobile_path, width=320)
                else:
                    st.warning("Mobile screenshot not found on disk.")

            # Session fingerprint routing information expander
            ua = perf.get("user_agent", "Default")
            proxy_used = perf.get("proxy", "Direct Connection") or "Direct Connection"
            with st.expander("🛡️ Session Fingerprint & Routing Details"):
                st.markdown(f"**Rotated User-Agent:**\n`{ua}`")
                st.markdown(f"**Rotated Proxy Server:**\n`{proxy_used}`")
                st.markdown(f"**HTTP Response Code:** `{data_payload.get('status_code', 200)}`")
                redirects = data_payload.get("redirect_chain") or perf.get("redirect_chain")
                if redirects:
                    st.markdown("**Redirect Chain Path:**")
                    for hop in redirects:
                        st.markdown(f"- `{hop.get('url')}` (HTTP `{hop.get('status')}`)")
                
                headers_dict = data_payload.get("response_headers", {})
                if headers_dict:
                    st.markdown("**Raw HTTP Response Headers:**")
                    st.json(headers_dict)

            with st.expander("🔄 Incremental Crawling & Delta Sync Details"):
                meta_dict = data_payload.get("metadata", {})
                sync_type_val = meta_dict.get("sync_type", "Full Sync")
                opt_signal = meta_dict.get("optimization_signal", "FULL_SYNC")
                c_hash = meta_dict.get("content_hash", "N/A")
                d_hash = meta_dict.get("dom_hash", "N/A")
                delta_dict = meta_dict.get("delta", {})
                
                st.markdown(f"**Sync Strategy:** `{sync_type_val}`")
                st.markdown(f"**Optimization Signal:** `{opt_signal}`")
                st.markdown(f"**Content Hashing (SHA-256):** `{c_hash}`")
                st.markdown(f"**DOM Layout Hashing (SHA-256):** `{d_hash}`")
                
                if delta_dict:
                    st.markdown("**Isolated Delta Fields (Modified):**")
                    st.json(delta_dict)
                else:
                    st.info("No delta variations extracted (hashes align or first crawl).")

        with layout_right:
            st.markdown("<h4 style='font-size: 0.95rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; margin-bottom: 14px;'>📊 Extracted Web Information Space</h4>", unsafe_allow_html=True)
            
            tab_text, tab_assets, tab_deep, tab_paywall, tab_telemetry, tab_json = st.tabs([
                "📝 Clean Site Text", 
                "🔗 Assets & Links", 
                "🧬 Deep Parsed Elements",
                "🛡️ Security & Paywalls",
                "🌐 Network & Telemetry Diagnostics",
                "💎 Perfect Validated JSON Code"
            ])
            
            with tab_text:
                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                
                # Deduplication summary metrics
                dq = data_payload.get("metadata", {}).get("data_quality_metrics", {})
                if dq:
                    st.markdown("##### ♻️ Content Deduplication Summary:")
                    dq_cols = st.columns(4)
                    with dq_cols[0]:
                        st.write("**Raw Text Len:**")
                        st.write(f"`{dq.get('raw_content_length', 0)} chars`")
                    with dq_cols[1]:
                        st.write("**Raw Paragraphs:**")
                        st.write(f"`{dq.get('raw_paragraphs_count', 0)}`")
                    with dq_cols[2]:
                        st.write("**Unique Paragraphs:**")
                        st.write(f"`{dq.get('dedup_paragraphs_count', 0)}`")
                    with dq_cols[3]:
                        st.write("**Deduplication Rate:**")
                        st.write(f"`{int(dq.get('dedup_rate', 1.0) * 100)}%`")
                    st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 16px 0;'>", unsafe_allow_html=True)

                st.markdown(f"<h3 style='color: #ffffff; font-weight: 700; margin-top: 0;'>{data_payload.get('title', 'N/A')}</h3>", unsafe_allow_html=True)
                st.caption(f"📅 Scraped At Time: `{data_payload.get('timestamp', 'N/A')}`")
                st.markdown("---")

                # Technical & SEO Properties
                st.markdown("##### 🔍 SEO & Technical Metadata:")
                seo_cols = st.columns(3)
                with seo_cols[0]:
                    st.write("**Canonical URL:**")
                    canonical_val = data_payload.get("canonical_url")
                    st.write(f"[{canonical_val}]({canonical_val})" if canonical_val else "None detected")
                with seo_cols[1]:
                    st.write("**Character Encoding:**")
                    st.write(f"`{data_payload.get('charset')}`" if data_payload.get('charset') else "None detected")
                with seo_cols[2]:
                    st.write("**HTTP Status Code:**")
                    st.write(f"`{data_payload.get('status_code')}`" if data_payload.get('status_code') else "None detected")
                
                kw_list = data_payload.get("keywords", [])
                if kw_list:
                    st.write("**Page Keywords:**")
                    st.write(", ".join([f"`{k}`" for k in kw_list]))
                st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 16px 0;'>", unsafe_allow_html=True)
                
                st.markdown("##### Page Hidden Meta Description Text:")
                m_desc = data_payload.get("metadata", {}).get("description", "")
                st.markdown(f"<p style='color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;'>{m_desc or 'No meta data descriptions embedded on target webpage source headers.'}</p>", unsafe_allow_html=True)
                st.markdown("<br>##### Clean Main Text Content Body Summary Preview:", unsafe_allow_html=True)
                st.info(data_payload.get("content", "No legible textual text pieces recovered."))
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_assets:
                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                st.markdown("### 🎨 Asset Gallery")
                
                gallery_tabs = st.tabs(["🖼️ Images", "🎬 Videos", "📄 Documents", "🏢 Logos"])
                
                # 🖼️ Images Tab
                with gallery_tabs[0]:
                    images_list = data_payload.get("images", [])
                    if not images_list:
                        st.write("No image data assets found on this targeted node context location.")
                    else:
                        for idx, img in enumerate(images_list):
                            is_healthy = img.get("healthy", True)
                            badge_color = "#10b981" if is_healthy else "#ef4444"
                            badge_text = "HEALTHY" if is_healthy else f"ISSUE: {img.get('issue', 'BROKEN').upper()}"
                            
                            local_path = img.get('local_path','')
                            file_name = local_path.split('/')[-1] if local_path else "unnamed"
                            with st.expander(f"🖼️ Image #{idx+1}: {file_name} (Status: {badge_text})"):
                                st.markdown(f"**Data Quality Status:** <span style='color: {badge_color}; font-weight: bold;'>{badge_text}</span>", unsafe_allow_html=True)
                                st.write(f"**Web Link Source URL:** {img.get('original_url') or img.get('url')}")
                                st.write(f"**Saved On Laptop Path:** `{local_path or 'Not downloaded'}`")
                                st.write(f"**File Format Type:** `{img.get('mime_type', 'N/A')}` | **File Size Weight:** `{img.get('file_size', 0)} bytes` | **Cache Version:** `{img.get('version', 1)}`")
                                
                                alt_val = img.get('alt_text') or img.get('alt')
                                width_val = img.get('width')
                                height_val = img.get('height')
                                st.write(f"**Description (Alt-Text):** `{alt_val or 'None specified'}`")
                                if width_val or height_val:
                                    st.write(f"**Visual Dimensions:** `{width_val or '?'}` x `{height_val or '?'}` pixels")
                                else:
                                    st.write("**Visual Dimensions:** `None specified`")
                                    
                                if local_path and os.path.exists(local_path):
                                    try:
                                        with open(local_path, "rb") as f:
                                            st.image(f.read(), use_container_width=True)
                                    except Exception:
                                        pass

                # 🎬 Videos Tab
                with gallery_tabs[1]:
                    videos_list = data_payload.get("videos", [])
                    if not videos_list:
                        st.write("No video attachments or streams found.")
                    else:
                        for idx, video in enumerate(videos_list):
                            original_url = video.get("original_url") or video.get("url") if isinstance(video, dict) else str(video)
                            local_path = video.get("local_path") if isinstance(video, dict) else None
                            file_name = local_path.split('/')[-1] if local_path else original_url.split('/')[-1]
                            
                            with st.expander(f"🎬 Video #{idx+1}: {file_name}"):
                                st.write(f"**Web Link Source URL:** {original_url}")
                                if local_path:
                                    st.write(f"**Saved On Laptop Path:** `{local_path}`")
                                    if os.path.exists(local_path):
                                        try:
                                            with open(local_path, "rb") as f:
                                                st.video(f.read())
                                        except Exception:
                                            pass
                                if not local_path and ("youtube.com" in original_url or "youtu.be" in original_url or "vimeo.com" in original_url):
                                    try:
                                        st.video(original_url)
                                    except Exception:
                                        pass

                # 📄 Documents Tab
                with gallery_tabs[2]:
                    documents_list = data_payload.get("documents", [])
                    if not documents_list:
                        st.write("No document attachments found on this target.")
                    else:
                        for idx, doc in enumerate(documents_list):
                            original_url = doc.get("original_url") or doc.get("url") if isinstance(doc, dict) else str(doc)
                            local_path = doc.get("local_path") if isinstance(doc, dict) else None
                            file_name = local_path.split('/')[-1] if local_path else original_url.split('/')[-1]
                            
                            with st.expander(f"📄 Document #{idx+1}: {file_name}"):
                                st.write(f"**Web Link Source URL:** {original_url}")
                                if local_path:
                                    st.write(f"**Saved On Laptop Path:** `{local_path}`")
                                    st.write(f"**File Size:** `{doc.get('file_size', 0)} bytes` | **MIME Type:** `{doc.get('mime_type', 'N/A')}`")
                                    if os.path.exists(local_path):
                                        try:
                                            with open(local_path, "rb") as f:
                                                st.download_button(
                                                    label="📥 Download Local File Attachment",
                                                    data=f.read(),
                                                    file_name=file_name,
                                                    mime=doc.get("mime_type", "application/octet-stream"),
                                                    key=f"doc_dl_{idx}"
                                                )
                                        except Exception:
                                            pass

                # 🏢 Logos Tab
                with gallery_tabs[3]:
                    logos_list = data_payload.get("logos", [])
                    if not logos_list:
                        st.write("No corporate logos or brand icon linkages discovered.")
                    else:
                        for idx, logo in enumerate(logos_list):
                            original_url = logo.get("original_url") or logo.get("url") if isinstance(logo, dict) else str(logo)
                            local_path = logo.get("local_path") if isinstance(logo, dict) else None
                            file_name = local_path.split('/')[-1] if local_path else original_url.split('/')[-1]
                            
                            with st.expander(f"🏢 Logo #{idx+1}: {file_name}"):
                                st.write(f"**Web Link Source URL:** {original_url}")
                                if local_path:
                                    st.write(f"**Saved On Laptop Path:** `{local_path}`")
                                if local_path and os.path.exists(local_path):
                                    try:
                                        with open(local_path, "rb") as f:
                                            st.image(f.read(), width=150)
                                    except Exception:
                                        pass
                                elif any(ext in original_url.lower() for ext in [".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"]):
                                    try:
                                        st.image(original_url, width=150)
                                    except Exception:
                                        pass
                
                st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 24px 0;'>", unsafe_allow_html=True)
                st.markdown("##### 🔗 Outgoing Links & Classifications")
                
                internal_links = data_payload.get("internal_links", [])
                with st.expander(f"🏠 Internal Domain Links ({len(internal_links)})"):
                    if not internal_links:
                        st.write("No internal domain links discovered.")
                    else:
                        for l in internal_links:
                            st.markdown(f"- [{l}]({l})")
                
                external_links = data_payload.get("external_links", [])
                with st.expander(f"🌐 External Outgoing Links ({len(external_links)})"):
                    if not external_links:
                        st.write("No external third-party links discovered.")
                    else:
                        for l in external_links:
                            st.markdown(f"- [{l}]({l})")

                download_links = data_payload.get("download_links", [])
                with st.expander(f"📥 Download Attachments / File Assets ({len(download_links)})"):
                    if not download_links:
                        st.write("No download attachment targets (.zip, .pdf, .csv, etc.) detected.")
                    else:
                        for l in download_links:
                            st.markdown(f"- [{l}]({l})")

                verified_links = data_payload.get("verified_links", [])
                with st.expander(f"🛡️ Link Status Verification ({len(verified_links)})"):
                    if not verified_links:
                        st.write("No link verification status available.")
                    else:
                        table_md = "| Verified Link URL | HTTP Status | Verdict |\n| :--- | :--- | :--- |\n"
                        for entry in verified_links:
                            url_str = entry.get("url", "")
                            status_code_str = str(entry.get("status_code")) if entry.get("status_code") is not None else "N/A"
                            status_str = entry.get("status", "unknown")
                            
                            if status_str == "active":
                                status_emoji = "🟢 Active"
                            else:
                                status_emoji = "🔴 Broken"
                                
                            table_md += f"| [{url_str}]({url_str}) | `{status_code_str}` | {status_emoji} |\n"
                        st.markdown(table_md)

                svgs_list = data_payload.get("svgs", [])
                with st.expander(f"📐 Inline Vector SVGs ({len(svgs_list)})"):
                    if not svgs_list:
                        st.write("No inline `<svg>` tags found in the DOM layout.")
                    else:
                        st.markdown("""
                            <style>
                                .svg-contrast-container {
                                    background: rgba(255, 255, 255, 0.08) !important;
                                    border: 1px solid rgba(255, 255, 255, 0.15) !important;
                                    border-radius: 8px !important;
                                    padding: 12px !important;
                                    display: inline-flex !important;
                                    align-items: center !important;
                                    justify-content: center !important;
                                    margin: 8px 0 !important;
                                }
                                .svg-contrast-container svg {
                                    filter: invert(1) !important;
                                }
                            </style>
                        """, unsafe_allow_html=True)
                        for idx, s in enumerate(svgs_list):
                            st.markdown(f"**SVG Icon #{idx+1}**")
                            st.markdown(f'<div class="svg-contrast-container">{s}</div>', unsafe_allow_html=True)
                            with st.expander("Show Raw SVG Code"):
                                st.code(s, language="xml")
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_deep:
                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                metadata_payload = data_payload.get("metadata", {})
                
                # Headings
                headings = metadata_payload.get("headings", [])
                if headings:
                    st.markdown("##### 🏷️ Headings (H1-H6)")
                    for h in headings[:15]:
                        st.markdown(f"- {h}")
                    if len(headings) > 15:
                        st.caption(f"... and {len(headings) - 15} more headings")
                    st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 16px 0;'>", unsafe_allow_html=True)

                # Social media og/twitter tags
                social = metadata_payload.get("social_metadata", {})
                if social:
                    st.markdown("##### 🌐 Social Media Metadata (OpenGraph & Twitter)")
                    for k, v in social.items():
                        st.markdown(f"**{k}**: `{v}`")
                    st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 16px 0;'>", unsafe_allow_html=True)

                # Lists
                lists = metadata_payload.get("lists", [])
                if lists:
                    st.markdown("##### 📋 Bullet / Numbered Lists")
                    for idx, l in enumerate(lists[:5]):
                        with st.expander(f"List ({l.get('type','ul')}) - {len(l.get('items', []))} items"):
                            for item in l.get("items", []):
                                st.write(f"- {item}")
                    st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 16px 0;'>", unsafe_allow_html=True)

                # Tables
                tables = data_payload.get("tables", [])
                if tables:
                    st.markdown("##### 📊 Extracted Web Data Tables")
                    for idx, t in enumerate(tables[:3]):
                        headers = t.get("headers", [])
                        rows = t.get("rows", [])
                        st.markdown(f"**Table #{idx+1} ({len(rows)} Rows)**")
                        if rows:
                            try:
                                import pandas as pd
                                df = pd.DataFrame(rows, columns=headers if len(headers) == len(rows[0]) else None)
                                st.dataframe(df, use_container_width=True)
                            except Exception:
                                st.write(t)
                        else:
                            st.write(t)
                    st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 16px 0;'>", unsafe_allow_html=True)

                # JSON-LD
                json_ld = metadata_payload.get("json_ld", [])
                if json_ld:
                    st.markdown("##### 💎 JSON-LD / Structured Schema Blocks")
                    for idx, jld in enumerate(json_ld[:3]):
                        with st.expander(f"JSON-LD block #{idx+1}"):
                            st.json(jld)

                if not any([headings, social, lists, tables, json_ld]):
                    st.info("No deep structured components (Lists, Tables, JSON-LD, Social Tags) resolved on the page.")
                
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_paywall:
                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                st.markdown("### 🛡️ Paywall Analytics & Security Diagnostics")
                
                meta_payload = data_payload.get("metadata", {})
                is_paywalled = meta_payload.get("is_paywalled", False)
                paywall_provider = meta_payload.get("paywall_provider")
                paywall_percentage = meta_payload.get("paywall_percentage", 0.0)
                paywall_teaser_text = meta_payload.get("paywall_teaser_text")
                
                if not is_paywalled:
                    st.markdown("""
                        <div style='display: flex; align-items: center; gap: 8px; margin-bottom: 16px;'>
                            <span style='background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); padding: 4px 12px; border-radius: 9999px; color: #10b981; font-size: 0.85rem; font-weight: 600;'>
                                ✅ No paywall detected
                            </span>
                        </div>
                    """, unsafe_allow_html=True)
                    st.success("The webpage does not appear to block content via a subscription or premium paywall.")
                else:
                    st.markdown("""
                        <div style='display: flex; align-items: center; gap: 8px; margin-bottom: 16px;'>
                            <span style='background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); padding: 4px 12px; border-radius: 9999px; color: #ef4444; font-size: 0.85rem; font-weight: 600;'>
                                ⚠️ Paywall Detected
                            </span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.write(f"**Paywall Provider:** `{paywall_provider or 'Unknown / Proprietary'}`")
                    
                    st.write(f"**Blocked Content Ratio:** `{paywall_percentage}%` of document paragraphs are locked.")
                    st.progress(paywall_percentage / 100.0)
                    
                    with st.expander("📝 Visible Teaser Text Preview"):
                        if paywall_teaser_text:
                            st.write(paywall_teaser_text)
                        else:
                            st.write("No teaser text found preceding the paywall container.")
                            
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_telemetry:
                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                st.markdown("### 🌐 Network & Telemetry Diagnostics")
                
                # Fetch telemetry data
                telemetry_data = data_payload.get("telemetry", {}) or data_payload.get("metadata", {}).get("telemetry", {})
                
                # 1. Failed Resources Log
                failed_res = telemetry_data.get("failed_resources", [])
                st.markdown(f"##### ⚠️ Failed Resources ({len(failed_res)})")
                if failed_res:
                    for res in failed_res:
                        st.markdown(
                            f"- **URL:** `{res.get('url')}`\n"
                            f"  - **Type:** `{res.get('resource_type')}`\n"
                            f"  - **Reason:** `{res.get('reason')}`" + (f" (HTTP `{res.get('status')}`)" if res.get('status') else "")
                        )
                else:
                    st.success("No failed resources (images, stylesheets, scripts) detected!")
                
                st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 24px 0;'>", unsafe_allow_html=True)
                
                # 2. Console Diagnostics Pipeline
                console_logs = telemetry_data.get("console_errors", [])
                st.markdown(f"##### 🖥️ Console Diagnostics ({len(console_logs)})")
                if console_logs:
                    for log in console_logs:
                        log_type = log.get("type", "error").upper()
                        color = "#ef4444" if log_type == "ERROR" else "#f59e0b"
                        st.markdown(
                            f"- <span style='color: {color}; font-weight: bold;'>[{log_type}]</span> {log.get('text')}\n"
                            f"  - *Location:* `{log.get('location', {})}`",
                            unsafe_allow_html=True
                        )
                else:
                    st.success("No console errors or warnings captured.")
                
                st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 24px 0;'>", unsafe_allow_html=True)
                
                # 3. HTTP Redirect Chain
                redirects = data_payload.get("redirect_chain", []) or perf.get("redirect_chain", [])
                st.markdown(f"##### 🔄 HTTP Redirect Chain ({len(redirects)})")
                if redirects:
                    for idx, hop in enumerate(redirects):
                        with st.expander(f"Hop {idx + 1}: {hop.get('url')} (HTTP {hop.get('status')})"):
                            st.write("**Outbound Request Headers:**")
                            st.json(hop.get("request_headers", {}))
                            st.write("**Inbound Response Headers:**")
                            st.json(hop.get("response_headers", {}))
                else:
                    st.info("No redirects occurred.")

                st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 24px 0;'>", unsafe_allow_html=True)

                # 3.5. Scale & Concurrency Infrastructure Diagnostics
                scale_diag = data_payload.get("metadata", {}).get("scale_diagnostics", {}) or {}
                st.markdown("##### 🚦 Scale & Concurrency Infrastructure Diagnostics")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(
                        label="Active Concurrency Slots",
                        value=scale_diag.get("active_concurrency_slots", 0)
                    )
                with col2:
                    st.metric(
                        label="Task Backlog Size",
                        value=scale_diag.get("task_backlog", 0)
                    )
                with col3:
                    st.metric(
                        label="Total Processed Tasks",
                        value=scale_diag.get("total_processed_tasks", 0)
                    )
                
                retries = scale_diag.get("retry_history", [])
                if retries:
                    st.markdown(f"###### 🔄 Retry Execution History ({len(retries)})")
                    for retry in retries:
                        backoff_val = retry.get('backoff_seconds')
                        backoff = f" (Backoff: `{backoff_val:.2f}s`)" if backoff_val is not None else ""
                        st.markdown(
                            f"- **Attempt {retry.get('attempt')}:** Classified `{retry.get('category')}` -> *{retry.get('reason')}*{backoff}\n"
                            f"  - *Error details:* `{retry.get('error')}`"
                        )
                else:
                    st.info("No network/transient retries occurred during this execution.")

                st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 24px 0;'>", unsafe_allow_html=True)

                # 4. Total Requests Captured
                with st.expander("🔍 Complete Outbound & Inbound Header Telemetry"):
                    st.write("**Outbound Requests Captured:**")
                    st.json(telemetry_data.get("requests", []))
                    st.write("**Inbound Responses Captured:**")
                    st.json(telemetry_data.get("responses", []))
                st.markdown("</div>", unsafe_allow_html=True)

            with tab_json:
                st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
                st.markdown("##### Perfect Validated Output JSON Tree Data Object")
                st.caption("Validated Pydantic instance verification tree view:")
                st.json(data_payload)
                st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown("""
        <div class='glass-card' style='text-align: center; padding: 80px 40px; border-style: dashed !important;'>
            <h3 style='color: #64748b; font-weight: 500; margin-bottom: 8px;'>AI Web Scraper is Ready to Work</h3>
            <p style='color: #475569; font-size: 1rem; margin: 0;'>Click '⚙️ Show Controls' at the top right to open your options configuration sidebar!</p>
        </div>
    """, unsafe_allow_html=True)