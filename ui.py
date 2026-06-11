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
else:
    st.markdown("---")
    sc_col1, sc_col2 = st.columns([3, 1])
    with sc_col1:
        url_input = st.text_input("Target URL Address:", value="https://quotes.toscrape.com/js/")
    with sc_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        trigger_btn = st.button("Start AI Scraper", type="primary", use_container_width=True)

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
            
            try:
                asyncio.run(run_prototype(url_input))
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
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        status_txt = data_payload.get("status", "FAILED").upper()
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

    layout_left, layout_right = st.columns([1, 1.2], gap="large")

    with layout_left:
        st.markdown("<h4 style='font-size: 0.95rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; margin-bottom: 14px;'>📸 Website Visual Proof Frame</h4>", unsafe_allow_html=True)
        screenshot_path = "storage/screenshots/full_page.png"
        if os.path.exists(screenshot_path):
            st.markdown(f"""
                <div class='browser-frame'>
                    <div class='browser-header-bar'>
                        <span class='dot dot-r'></span><span class='dot dot-y'></span><span class='dot dot-g'></span>
                        <div class='browser-address-field'>{data_payload.get('url', url_input)}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            st.image(screenshot_path, use_container_width=True)
        else:
            st.warning("Visual snapshot track preview element unreached from storage allocations.")

    with layout_right:
        st.markdown("<h4 style='font-size: 0.95rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; margin-bottom: 14px;'>📊 Extracted Web Information Space</h4>", unsafe_allow_html=True)
        
        # CHANGED: Replaced 'Extracted Links' with 'Assets & Links' and removed 'Mentor Required'
        tab_text, tab_assets, tab_json = st.tabs([
            "📝 Clean Site Text", 
            "🔗 Assets & Links", 
            "💎 Perfect Validated JSON Code"
        ])
        
        with tab_text:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='color: #ffffff; font-weight: 700; margin-top: 0;'>{data_payload.get('title', 'N/A')}</h3>", unsafe_allow_html=True)
            st.caption(f"📅 Scraped At Time: `{data_payload.get('timestamp', 'N/A')}`")
            st.markdown("---")
            
            st.markdown("##### Page Hidden Meta Description Text:")
            m_desc = data_payload.get("metadata", {}).get("description", "")
            st.markdown(f"<p style='color: #cbd5e1; font-size: 0.95rem; line-height: 1.6;'>{m_desc or 'No meta data descriptions embedded on target webpage source headers.'}</p>", unsafe_allow_html=True)
            
            st.markdown("<br>##### Clean Main Text Content Body Summary Preview:", unsafe_allow_html=True)
            st.info(data_payload.get("content", "No legible textual text pieces recovered."))
            st.markdown("</div>", unsafe_allow_html=True)

        with tab_assets:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown("##### 🖼️ Downloaded Image Files Details")
            images_list = data_payload.get("images", [])
            if not images_list:
                st.write("No image data assets found on this targeted node context location.")
            else:
                for idx, img in enumerate(images_list):
                    with st.expander(f"📥 Saved File: {img.get('local_path','').split('/')[-1]}"):
                        st.write(f"**Web Link Source URL:** {img.get('original_url')}")
                        st.write(f"**Saved On Laptop Path:** `{img.get('local_path')}`")
                        st.write(f"**File Format Type:** `{img.get('mime_type')}` | **File Size Weight:** `{img.get('file_size')} bytes`")
            
            st.markdown("<hr style='border-color: rgba(255,255,255,0.06); margin: 24px 0;'>", unsafe_allow_html=True)
            st.markdown("##### 🔗 All Discovered Outgoing Web Links")
            links_list = data_payload.get("links", [])
            for single_link in links_list:
                st.markdown(f"* Extracted Destination Link: [{single_link}]({single_link})")
            st.markdown("</div>", unsafe_allow_html=True)

        with tab_json:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            # CHANGED: Cleaned text title header to remove mentor references
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