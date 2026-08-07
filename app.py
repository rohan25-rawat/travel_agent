import re
import io
import sys
from datetime import date

# Force UTF-8 stdout/stderr. On Windows, the console often defaults to
# cp1252/ascii, which raises UnicodeEncodeError as soon as any emoji or
# non-ASCII character (₹, ✈️, etc.) gets printed/logged.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests
import streamlit as st
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from tavily import TavilyClient
from langchain.agents import create_agent

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

# ------------------------------------------------------------
# PAGE
# ------------------------------------------------------------

st.set_page_config(page_title="AI Trip Planner", page_icon="✈️", layout="wide")

# ------------------------------------------------------------
# STYLING (dark theme, muted red)
# ------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp {
        background-image:
            linear-gradient(rgba(0, 0, 0, 0.72), rgba(0, 0, 0, 0.72)),
            url('https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=1920&q=80');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }

    .trip-title {
        font-size: 2.6rem;
        font-weight: 800;
        color: #ffffff;
        text-shadow: 0 0 10px rgba(0, 0, 0, 0.8);
        margin-bottom: 0;
        position: relative;
        z-index: 2;
    }
    .trip-caption {
        position: relative;
        z-index: 2;
        color: #e6e6e6;
        font-size: 1.05rem;
    }

    /* Colorful buttons (hover transition only, no looping animation) */
    div.stButton > button, div.stDownloadButton > button {
        background: linear-gradient(90deg, #ff6b6b, #f7b733, #4facfe, #43e97b, #ff6b6b);
        background-size: 250% auto;
        color: white !important;
        border: none;
        border-radius: 12px;
        padding: 0.6em 1.2em;
        font-weight: 700;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        transition: background-position 0.4s ease, transform 0.2s ease;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-position: right center;
        transform: translateY(-2px) scale(1.02);
    }

    section[data-testid="stSidebar"] {
        background: rgba(0, 0, 0, 0.85);
    }
    section[data-testid="stSidebar"] * {
        color: #f5f5f5 !important;
    }

    .block-container {
        position: relative;
        z-index: 2;
    }
    .block-container, .block-container p, .block-container li {
        color: #f5f5f5;
    }
    .block-container h1, .block-container h2, .block-container h3,
    .block-container h4, .block-container strong {
        color: #ffffff;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 10px;
    }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="trip-title">✈️ AI Trip Planner</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="trip-caption">AI-powered travel planning with live web, weather and places data.</div>',
    unsafe_allow_html=True,
)
st.write("")

# ------------------------------------------------------------
# SESSION STATE
# ------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "connected" not in st.session_state:
    st.session_state.connected = False
if "last_itinerary" not in st.session_state:
    st.session_state.last_itinerary = ""
if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = {}

# ------------------------------------------------------------
# SIDEBAR API KEYS
# ------------------------------------------------------------

with st.sidebar:
    st.header("🔑 API Configuration")
    google_key = st.text_input("Gemini API Key", type="password", value=st.session_state["api_keys"].get("google", ""))
    geo_key = st.text_input("Geoapify API Key", type="password", value=st.session_state["api_keys"].get("geo", ""))
    tavily_key = st.text_input("Tavily API Key", type="password", value=st.session_state["api_keys"].get("tavily", ""))
    weather_key = st.text_input("OpenWeather API Key", type="password", value=st.session_state["api_keys"].get("weather", ""))

    if st.button("🔌 Connect APIs", use_container_width=True):
        if all([google_key, geo_key, tavily_key, weather_key]):
            st.session_state["api_keys"] = {
                "google": google_key,
                "geo": geo_key,
                "tavily": tavily_key,
                "weather": weather_key
            }
            st.session_state.connected = True
            st.success("APIs connected!")
            st.rerun()
        else:
            st.error("Please enter all API keys.")

# ------------------------------------------------------------
# MAIN APPLICATION INTERFACE
# ------------------------------------------------------------

if not st.session_state.connected:
    st.info("👈 Enter your API keys in the sidebar and click **Connect APIs** to start planning!")
else:
    # ------------------------------------------------------------
    # Snapshot keys into local variables. Tool functions must NOT read
    # st.session_state directly at call time — LangChain may invoke tools
    # (and the model) from a worker thread where Streamlit's session_state
    # is not accessible, causing "session_state has no key ..." errors.
    # Closures over plain local variables avoid that entirely.
    # ------------------------------------------------------------
    GOOGLE_KEY = st.session_state["api_keys"]["google"]
    GEO_KEY = st.session_state["api_keys"]["geo"]
    TAVILY_KEY = st.session_state["api_keys"]["tavily"]
    WEATHER_KEY = st.session_state["api_keys"]["weather"]

    # ------------------------------------------------------------
    # TOOLS DEFINITION
    # ------------------------------------------------------------

    @tool
    def places_tool(city_or_location: str, category: str = "tourism.sights"):
        """Find tourist attractions and places given a city name or address."""
        geo_url = "https://api.geoapify.com/v1/geocode/search"
        geo_params = {"text": city_or_location, "apiKey": GEO_KEY}
        try:
            geo_res = requests.get(geo_url, params=geo_params, timeout=10).json()
            if not geo_res.get("features"):
                return {"error": "Location not found"}

            lon, lat = geo_res["features"][0]["geometry"]["coordinates"]

            places_url = "https://api.geoapify.com/v2/places"
            places_params = {
                "categories": category,
                "filter": f"circle:{lon},{lat},10000",
                "limit": 10,
                "apiKey": GEO_KEY
            }
            r = requests.get(places_url, params=places_params, timeout=15)
            if r.status_code != 200:
                return {"error": r.text}
            return [
                {"name": x["properties"].get("name", "Unknown"),
                 "address": x["properties"].get("formatted", "")}
                for x in r.json().get("features", [])
            ]
        except Exception as e:
            return {"error": str(e)}

    @tool
    def weather_tool(city: str):
        """Get weather forecast for a city."""
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {"q": city, "appid": WEATHER_KEY, "units": "metric"}
        try:
            r = requests.get(url, params=params, timeout=15)
            if r.status_code != 200:
                return {"error": r.text}
            return [
                {"time": x.get("dt_txt"),
                 "temperature": x["main"].get("temp"),
                 "condition": x["weather"][0].get("description")}
                for x in r.json().get("list", [])[:8]
            ]
        except Exception as e:
            return {"error": str(e)}

    @tool
    def search_tool(query: str):
        """Search current travel information."""
        try:
            client = TavilyClient(api_key=TAVILY_KEY)
            return client.search(query=query, search_depth="advanced", max_results=5)
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------
    # AGENT INITIALIZATION
    # ------------------------------------------------------------

    SYSTEM_PROMPT = """
You are a professional AI Trip Planner.
Create practical day-wise itineraries.
Use your tools when useful.

Consider:
- destination
- start date
- budget
- number of days
- attractions
- restaurants
- weather
- current travel information

IMPORTANT: Return ONLY clean Markdown using exactly this structure:

# ✈️ Trip Summary

**Destination:** ...
**Start Date:** ...
**Duration:** ...
**Budget:** ...

---

# 📅 Day 1

### 🌅 Morning
**Place:** ...
**Activity:** ...
**Estimated Cost:** ...

### ☀️ Afternoon
**Place:** ...
**Activity:** ...
**Estimated Cost:** ...

### 🌆 Evening
**Place:** ...
**Activity:** ...
**Estimated Cost:** ...

### 🍴 Food
...

### 🌤️ Weather
...

---

# 💰 Budget Summary

| Category | Estimated Cost |
|---|---:|
| Accommodation | ... |
| Food | ... |
| Transport | ... |
| Attractions | ... |
| Other | ... |
| **Total** | **...** |

# 💡 Travel Tips

- ...
"""

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            google_api_key=GOOGLE_KEY,
            temperature=0.2
        )
        agent = create_agent(
            model=llm,
            tools=[places_tool, weather_tool, search_tool],
            system_prompt=SYSTEM_PROMPT
        )
    except Exception as e:
        st.error(f"Agent initialization error: {e}")
        st.stop()

    # ------------------------------------------------------------
    # TRIP INPUTS IN SIDEBAR
    # ------------------------------------------------------------

    st.sidebar.divider()
    st.sidebar.header("🌍 Trip Details")
    destination = st.sidebar.text_input("📍 Destination", placeholder="Example: Jaipur")
    trip_start_date = st.sidebar.date_input("🗓️ Start Date", value=date.today())
    budget = st.sidebar.number_input("💰 Budget (INR)", min_value=1000, value=20000, step=1000)
    days = st.sidebar.number_input("📅 Number of Days", min_value=1, max_value=15, value=3)

    # ------------------------------------------------------------
    # PDF GENERATION
    # ------------------------------------------------------------

    def sanitize_pdf_text(text: str) -> str:
        """Replace characters that standard PDF fonts can't render (emoji, ₹, etc.)."""
        replacements = {
            "₹": "Rs. ",
            "—": "-",
            "–": "-",
            "’": "'",
            "“": '"',
            "”": '"',
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        # Drop any remaining non-Latin-1 characters (emojis, etc.)
        return text.encode("latin-1", "ignore").decode("latin-1")

    def clean_inline(text: str) -> str:
        text = sanitize_pdf_text(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        # Escape any stray angle brackets that aren't our bold tags
        return text

    def parse_table(table_lines):
        rows = []
        for l in table_lines:
            if re.match(r"^\|[\s\-:|]+\|$", l.strip()):
                continue
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            cells = [sanitize_pdf_text(re.sub(r"\*\*(.+?)\*\*", r"\1", c)) for c in cells]
            rows.append(cells)
        return rows

    def markdown_to_pdf(md_text: str) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=colors.HexColor("#1a6b2e"))
        h3 = ParagraphStyle("H3", parent=styles["Heading3"], textColor=colors.HexColor("#1a1a1a"))
        body = styles["BodyText"]
        story = []

        lines = md_text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if not line.strip():
                story.append(Spacer(1, 6))
                i += 1
                continue
            if line.startswith("### "):
                story.append(Paragraph(clean_inline(line[4:]), h3))
            elif line.startswith("## "):
                story.append(Paragraph(clean_inline(line[3:]), h3))
            elif line.startswith("# "):
                story.append(Paragraph(clean_inline(line[2:]), h1))
            elif line.strip() == "---":
                story.append(Spacer(1, 10))
            elif line.strip().startswith("|"):
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i])
                    i += 1
                table_data = parse_table(table_lines)
                if table_data:
                    t = Table(table_data, hAlign="LEFT")
                    t.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    story.append(t)
                    story.append(Spacer(1, 8))
                continue
            elif line.strip().startswith("- "):
                story.append(Paragraph("• " + clean_inline(line.strip()[2:]), body))
            else:
                story.append(Paragraph(clean_inline(line), body))
            i += 1

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    # ------------------------------------------------------------
    # DISPLAY HELPERS
    # ------------------------------------------------------------

    def render_itinerary(markdown_text):
        parts = re.split(r"(?m)^# (.+)$", markdown_text)
        sections = list(zip(parts[1::2], parts[2::2]))

        if not sections:
            st.markdown(markdown_text)
            return

        for title, body in sections:
            body = body.strip()
            clean_title = re.sub(r"[^\w\s]", "", title).strip()

            if "Trip Summary" in title:
                st.markdown(f"### {title}")
                dest = re.search(r"\*\*Destination:\*\*\s*(.+)", body)
                start_d = re.search(r"\*\*Start Date:\*\*\s*(.+)", body)
                dur = re.search(r"\*\*Duration:\*\*\s*(.+)", body)
                bud = re.search(r"\*\*Budget:\*\*\s*(.+)", body)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("📍 Destination", dest.group(1).strip() if dest else "—")
                c2.metric("🗓️ Start Date", start_d.group(1).strip() if start_d else "—")
                c3.metric("📅 Duration", dur.group(1).strip() if dur else "—")
                c4.metric("💰 Budget", bud.group(1).strip() if bud else "—")
                st.divider()

            elif re.match(r"Day\s+\d+", clean_title):
                with st.expander(f"{title}", expanded=("Day 1" in title)):
                    st.markdown(body)

            else:
                st.markdown(f"### {title}")
                st.markdown(body)
                st.divider()

    def extract_text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [b if isinstance(b, str) else b.get("text", "") for b in content]
            return "\n".join(parts)
        return str(content)

    def run_agent(prompt_text, spinner_text):
        st.session_state.messages.append({"role": "user", "content": prompt_text})
        with st.spinner(spinner_text):
            try:
                response = agent.invoke({"messages": st.session_state.messages})
                answer = extract_text(response["messages"][-1].content)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                st.session_state.last_itinerary = answer
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error during execution: {e}")

    # ------------------------------------------------------------
    # ACTIONS & RENDER
    # ------------------------------------------------------------

    if st.sidebar.button("✨ Generate Trip", use_container_width=True):
        if not destination:
            st.warning("Please enter a destination.")
        else:
            prompt = (
                f"Plan a {days}-day trip to {destination} starting on "
                f"{trip_start_date.strftime('%B %d, %Y')}. Budget: ₹{budget}."
            )
            st.session_state.messages = []
            st.session_state.last_itinerary = ""
            run_agent(prompt, "🤖 Creating your itinerary...")

    if st.sidebar.button("🗑️ Clear Trip", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_itinerary = ""
        st.rerun()

    # Render generated itinerary
    if st.session_state.last_itinerary:
        render_itinerary(st.session_state.last_itinerary)

        pdf_bytes = markdown_to_pdf(st.session_state.last_itinerary)
        st.download_button(
            label="⬇️ Download Itinerary (PDF)",
            data=pdf_bytes,
            file_name=f"{re.sub(r'[^\w\-]+', '_', destination or 'trip')}_itinerary.pdf",
            mime="application/pdf",
            use_container_width=False,
        )

        st.divider()
        st.subheader("💬 Modify Your Trip")
        st.caption("Example: Make Day 2 cheaper or add more local food spots.")

        message = st.chat_input("Ask the trip planner...")
        if message:
            run_agent(message, "🤖 Updating your plan...")
