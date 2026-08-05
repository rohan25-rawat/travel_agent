```python
import streamlit as st
import requests
from tavily import TavilyClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain.agents import create_agent

# ------------------------------------------------------------
# PAGE
# ------------------------------------------------------------

st.set_page_config(
    page_title="AI Trip Planner",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ AI Trip Planner")
st.caption("AI-powered travel planning with live web, weather and places data.")


# ------------------------------------------------------------
# SESSION
# ------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "connected" not in st.session_state:
    st.session_state.connected = False


# ------------------------------------------------------------
# API KEYS
# ------------------------------------------------------------

with st.sidebar:

    st.header("🔑 API Configuration")

    google_key = st.text_input(
        "Gemini API Key",
        type="password"
    )

    geo_key = st.text_input(
        "Geoapify API Key",
        type="password"
    )

    tavily_key = st.text_input(
        "Tavily API Key",
        type="password"
    )

    weather_key = st.text_input(
        "OpenWeather API Key",
        type="password"
    )

    if st.button(
        "🔌 Connect APIs",
        use_container_width=True
    ):

        if all([
            google_key,
            geo_key,
            tavily_key,
            weather_key
        ]):

            st.session_state.connected = True
            st.success("APIs connected!")

        else:

            st.error("Please enter all API keys.")


if not st.session_state.connected:

    st.info("👈 Enter your API keys in the sidebar.")
    st.stop()


# ------------------------------------------------------------
# TOOLS
# ------------------------------------------------------------

def places(lat, lon, category="tourism.sights"):

    url = "https://api.geoapify.com/v2/places"

    params = {
        "categories": category,
        "filter": f"circle:{lon},{lat},10000",
        "limit": 10,
        "apiKey": geo_key
    }

    try:

        r = requests.get(
            url,
            params=params,
            timeout=15
        )

        if r.status_code != 200:
            return {"error": r.text}

        return [
            {
                "name": x["properties"].get(
                    "name",
                    "Unknown"
                ),
                "address": x["properties"].get(
                    "formatted",
                    ""
                )
            }
            for x in r.json().get(
                "features",
                []
            )
        ]

    except Exception as e:

        return {"error": str(e)}


def weather(city):

    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "q": city,
        "appid": weather_key,
        "units": "metric"
    }

    try:

        r = requests.get(
            url,
            params=params,
            timeout=15
        )

        if r.status_code != 200:
            return {"error": r.text}

        return [
            {
                "time": x.get("dt_txt"),
                "temperature": x["main"].get("temp"),
                "condition": x["weather"][0].get(
                    "description"
                )
            }
            for x in r.json().get("list", [])[:8]
        ]

    except Exception as e:

        return {"error": str(e)}


def web_search(query):

    try:

        client = TavilyClient(
            api_key=tavily_key
        )

        return client.search(
            query=query,
            search_depth="advanced",
            max_results=5
        )

    except Exception as e:

        return {"error": str(e)}


# ------------------------------------------------------------
# LANGCHAIN TOOLS
# ------------------------------------------------------------

@tool
def places_tool(
    lat: float,
    lon: float,
    category: str = "tourism.sights"
):
    """Find tourist attractions and places."""
    return places(lat, lon, category)


@tool
def weather_tool(city: str):
    """Get weather forecast for a city."""
    return weather(city)


@tool
def search_tool(query: str):
    """Search current travel information."""
    return web_search(query)


# ------------------------------------------------------------
# AGENT
# ------------------------------------------------------------

try:

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=google_key,
        temperature=0.2
    )

    agent = create_agent(
        model=llm,
        tools=[
            places_tool,
            weather_tool,
            search_tool
        ],
        system_prompt="""
You are a professional AI Trip Planner.

Create practical day-wise itineraries.

Use your tools when useful.

Consider:
- destination
- budget
- number of days
- attractions
- restaurants
- weather
- current travel information

Group nearby locations together.

Keep the itinerary realistic.

IMPORTANT:
Return ONLY clean Markdown.

Use exactly this structure:

# ✈️ Trip Summary

**Destination:** ...
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

Repeat the same format for every day.

At the end provide:

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
- ...
- ...

Do not add unnecessary explanations.
"""
    )

except Exception as e:

    st.error(f"Agent initialization error: {e}")
    st.stop()


# ------------------------------------------------------------
# TRIP INPUT
# ------------------------------------------------------------

st.sidebar.divider()
st.sidebar.header("🌍 Trip Details")

destination = st.sidebar.text_input(
    "📍 Destination",
    placeholder="Example: Jaipur"
)

budget = st.sidebar.number_input(
    "💰 Budget (INR)",
    min_value=1000,
    value=20000,
    step=1000
)

days = st.sidebar.number_input(
    "📅 Number of Days",
    min_value=1,
    max_value=15,
    value=3
)


# ------------------------------------------------------------
# GENERATE ITINERARY
# ------------------------------------------------------------

if st.sidebar.button(
    "✨ Generate Trip",
    use_container_width=True
):

    if not destination:

        st.warning(
            "Please enter a destination."
        )
        st.stop()

    prompt = f"""
Plan a {days}-day trip to {destination}.

Budget: ₹{budget}

Use your tools to get current information.

Research:
1. Tourist attractions
2. Restaurants / food
3. Weather
4. Current travel information

Create a realistic itinerary.

Keep the total estimated cost
within ₹{budget} where possible.

Follow the exact Markdown format
defined in your system instructions.
"""

    st.session_state.messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]

    with st.spinner(
        "🤖 Creating your itinerary..."
    ):

        try:

            response = agent.invoke({
                "messages": st.session_state.messages
            })

            answer = response[
                "messages"
            ][-1].content

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer
            })

            st.markdown(answer)

        except Exception as e:

            st.error(
                f"❌ Failed to generate itinerary: {e}"
            )


# ------------------------------------------------------------
# FOLLOW-UP
# ------------------------------------------------------------

if st.session_state.messages:

    st.divider()

    st.subheader("💬 Modify Your Trip")

    st.caption(
        "Example: Make Day 2 cheaper or replace a restaurant."
    )

    message = st.chat_input(
        "Ask the trip planner..."
    )

    if message:

        st.session_state.messages.append({
            "role": "user",
            "content": message
        })

        with st.spinner(
            "🤖 Updating..."
        ):

            try:

                response = agent.invoke({
                    "messages": st.session_state.messages
                })

                answer = response[
                    "messages"
                ][-1].content

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })

                st.markdown(answer)

            except Exception as e:

                st.error(
                    f"❌ Error: {e}"
                )


# ------------------------------------------------------------
# CLEAR
# ------------------------------------------------------------

if st.sidebar.button(
    "🗑️ Clear Trip",
    use_container_width=True
):

    st.session_state.messages = []
    st.rerun()
```
