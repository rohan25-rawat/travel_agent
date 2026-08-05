
import streamlit as st
import requests

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain.agents import create_agent
from tavily import TavilyClient


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="AI Trip Planner",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ AI Trip Planner")
st.caption(
    "Plan personalized trips using Gemini + Geoapify + "
    "Weather + Tavily."
)


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "connected" not in st.session_state:
    st.session_state.connected = False


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("🔑 API Keys")

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
        if not all([
            google_key,
            geo_key,
            tavily_key,
            weather_key
        ]):
            st.error("Please enter all API keys.")
        else:
            st.session_state.connected = True
            st.success("✅ APIs connected!")


# ============================================================
# STOP UNTIL API KEYS ARE ENTERED
# ============================================================

if not st.session_state.connected:

    st.info(
        "👈 Enter your four API keys in the sidebar "
        "and click **Connect APIs**."
    )

    st.stop()


# ============================================================
# GEOAPIFY
# ============================================================

def search_places(
    lat,
    lon,
    category="tourism.sights",
    radius=5000
):

    url = "https://api.geoapify.com/v2/places"

    params = {
        "categories": category,
        "filter": f"circle:{lon},{lat},{radius}",
        "limit": 10,
        "apiKey": geo_key
    }

    try:
        r = requests.get(
            url,
            params=params,
            timeout=20
        )

        if r.status_code != 200:
            return {"error": r.text}

        places = []

        for item in r.json().get("features", []):

            p = item.get("properties", {})

            places.append({
                "name": p.get("name", "Unknown"),
                "address": p.get("formatted", ""),
                "latitude": p.get("lat"),
                "longitude": p.get("lon"),
                "categories": p.get("categories", [])
            })

        return places

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# WEATHER
# ============================================================

def get_weather(city):

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
            timeout=20
        )

        if r.status_code != 200:
            return {"error": r.text}

        data = r.json()
        result = []

        for x in data.get("list", [])[:8]:

            result.append({
                "datetime": x.get("dt_txt"),
                "temperature": x["main"].get("temp"),
                "feels_like": x["main"].get("feels_like"),
                "humidity": x["main"].get("humidity"),
                "weather": x["weather"][0].get(
                    "description"
                ),
                "rain_probability": x.get("pop", 0)
            })

        return result

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# TAVILY
# ============================================================

def web_search(query):

    try:

        client = TavilyClient(
            api_key=tavily_key
        )

        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True
        )

        return {
            "answer": response.get("answer"),
            "results": [
                {
                    "title": x.get("title"),
                    "url": x.get("url"),
                    "content": x.get("content")
                }
                for x in response.get("results", [])
            ]
        }

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# LANGCHAIN TOOLS
# ============================================================

@tool
def places_tool(
    lat: float,
    lon: float,
    category: str = "tourism.sights",
    radius: int = 5000
):
    """Find tourist attractions, restaurants and places."""
    return search_places(
        lat,
        lon,
        category,
        radius
    )


@tool
def weather_tool(city: str):
    """Get the current forecast for a city."""
    return get_weather(city)


@tool
def travel_search(query: str):
    """Search current travel information on the web."""
    return web_search(query)


tools = [
    places_tool,
    weather_tool,
    travel_search
]


# ============================================================
# GEMINI AGENT
# ============================================================

try:

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=google_key,
        temperature=0.3
    )

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt="""
You are an expert AI Trip Planner.

Create realistic, personalized and
budget-conscious travel itineraries.

Use your tools whenever useful.

Use:
- places_tool for attractions/restaurants
- weather_tool for weather
- travel_search for current travel information

Consider destination, budget, days,
interests, travel style, weather and
travel time.

Group nearby places together.

Avoid overcrowding each day.

For each day include:

Morning
Afternoon
Evening
Places
Food
Estimated cost
Weather considerations

Also provide:

Total estimated budget
Food recommendations
Travel tips
Current travel information

Do not invent current information
when it can be checked using tools.
"""
    )

except Exception as e:

    st.error(f"Agent error: {e}")
    st.stop()


# ============================================================
# TRIP INPUTS
# ============================================================

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
    "📅 Days",
    min_value=1,
    max_value=30,
    value=3
)

interests = st.sidebar.multiselect(
    "❤️ Interests",
    [
        "History",
        "Food",
        "Photography",
        "Nature",
        "Adventure",
        "Shopping",
        "Beaches",
        "Nightlife",
        "Culture"
    ],
    default=["History", "Food"]
)

style = st.sidebar.selectbox(
    "🚗 Travel Style",
    [
        "Budget-friendly",
        "Comfort",
        "Luxury"
    ]
)


# ============================================================
# GENERATE
# ============================================================

if st.sidebar.button(
    "✨ Generate Itinerary",
    use_container_width=True
):

    if not destination:
        st.warning("Please enter a destination.")
        st.stop()

    if not interests:
        st.warning("Select at least one interest.")
        st.stop()

    interest_text = ", ".join(interests)

    prompt = f"""
Plan a complete {days}-day trip.

Destination: {destination}
Budget: ₹{budget}
Interests: {interest_text}
Travel style: {style}

Use your tools to research the destination.

Create a realistic day-wise itinerary.

For every day include:

### Day X
**Morning**
- Activity
- Place
- Cost

**Afternoon**
- Activity
- Place
- Cost

**Evening**
- Activity
- Place
- Cost

**Food**
- Recommendations

**Weather**
- Weather considerations

Also provide:

### Budget Breakdown
- Accommodation
- Food
- Transport
- Attractions
- Miscellaneous

### Travel Tips
Include useful current information.

Try to stay within the user's budget.
"""

    st.session_state.messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]

    with st.spinner(
        "🤖 Planning your trip..."
    ):

        try:

            response = agent.invoke({
                "messages": st.session_state.messages
            })

            answer = response["messages"][-1].content

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer
            })

            st.success("🎉 Itinerary ready!")

            st.markdown(answer)

        except Exception as e:

            st.error(
                f"❌ Failed to generate itinerary: {e}"
            )


# ============================================================
# FOLLOW-UP CHAT
# ============================================================

if st.session_state.messages:

    st.divider()

    st.subheader("💬 Modify Your Trip")

    st.caption(
        "Example: Make Day 2 cheaper, add restaurants, "
        "or replace an outdoor activity."
    )

    user_message = st.chat_input(
        "Ask something about your trip..."
    )

    if user_message:

        st.session_state.messages.append({
            "role": "user",
            "content": user_message
        })

        with st.spinner(
            "🤖 Updating your itinerary..."
        ):

            try:

                response = agent.invoke({
                    "messages": st.session_state.messages
                })

                answer = response["messages"][-1].content

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })

                st.markdown(answer)

            except Exception as e:

                st.error(
                    f"❌ Error: {e}"
                )


# ============================================================
# CLEAR
# ============================================================

if st.sidebar.button(
    "🗑️ Clear Conversation",
    use_container_width=True
):

    st.session_state.messages = []
    st.rerun()

