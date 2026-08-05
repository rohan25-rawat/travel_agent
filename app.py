```python
import streamlit as st
import requests

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain.agents import create_agent
from tavily import TavilyClient


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="AI Trip Planner",
    page_icon="✈️",
    layout="wide"
)


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "api_connected" not in st.session_state:
    st.session_state.api_connected = False


# ============================================================
# SIDEBAR - API KEYS
# ============================================================

with st.sidebar:

    st.header("🔑 API Configuration")

    st.caption(
        "Enter your API keys below. "
        "They are not stored in GitHub."
    )

    google_api_key = st.text_input(
        "Google Gemini API Key",
        type="password",
        placeholder="Enter Gemini API key"
    )

    geoapify_api_key = st.text_input(
        "Geoapify API Key",
        type="password",
        placeholder="Enter Geoapify API key"
    )

    tavily_api_key = st.text_input(
        "Tavily API Key",
        type="password",
        placeholder="Enter Tavily API key"
    )

    openweather_api_key = st.text_input(
        "OpenWeather API Key",
        type="password",
        placeholder="Enter OpenWeather API key"
    )

    connect_button = st.button(
        "🔌 Connect APIs",
        use_container_width=True
    )

    if connect_button:

        if not google_api_key:
            st.error("Google Gemini API key is required.")

        elif not geoapify_api_key:
            st.error("Geoapify API key is required.")

        elif not tavily_api_key:
            st.error("Tavily API key is required.")

        elif not openweather_api_key:
            st.error("OpenWeather API key is required.")

        else:

            st.session_state.api_connected = True

            st.success("✅ APIs connected successfully!")


# ============================================================
# CHECK API CONNECTION
# ============================================================

if not st.session_state.api_connected:

    st.title("✈️ AI Trip Planner")

    st.info(
        "👈 Enter your API keys in the sidebar "
        "and click **Connect APIs** to start."
    )

    st.stop()


# ============================================================
# GEOAPIFY
# ============================================================

def search_places(
    lat: float,
    lon: float,
    category: str = "tourism.sights",
    radius: int = 5000
):

    url = "https://api.geoapify.com/v2/places"

    params = {
        "categories": category,
        "filter": f"circle:{lon},{lat},{radius}",
        "limit": 10,
        "apiKey": geoapify_api_key
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        if response.status_code != 200:

            return {
                "error": response.text
            }

        data = response.json()

        places = []

        for feature in data.get("features", []):

            properties = feature.get(
                "properties",
                {}
            )

            places.append({

                "name": properties.get(
                    "name",
                    "Unknown"
                ),

                "address": properties.get(
                    "formatted",
                    "Address unavailable"
                ),

                "latitude": properties.get(
                    "lat"
                ),

                "longitude": properties.get(
                    "lon"
                ),

                "categories": properties.get(
                    "categories",
                    []
                )
            })

        return places

    except Exception as e:

        return {
            "error": str(e)
        }


# ============================================================
# WEATHER
# ============================================================

def get_weather(city: str):

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
    )

    params = {

        "q": city,

        "appid": openweather_api_key,

        "units": "metric"
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        if response.status_code != 200:

            return {
                "error": response.text
            }

        data = response.json()

        weather_data = []

        for item in data.get("list", [])[:8]:

            weather_data.append({

                "datetime": item.get(
                    "dt_txt"
                ),

                "temperature": item[
                    "main"
                ].get("temp"),

                "feels_like": item[
                    "main"
                ].get("feels_like"),

                "humidity": item[
                    "main"
                ].get("humidity"),

                "weather": item[
                    "weather"
                ][0].get(
                    "description"
                ),

                "rain_probability": item.get(
                    "pop",
                    0
                )
            })

        return weather_data

    except Exception as e:

        return {
            "error": str(e)
        }


# ============================================================
# TAVILY
# ============================================================

def search_travel_info(query: str):

    try:

        tavily_client = TavilyClient(
            api_key=tavily_api_key
        )

        response = tavily_client.search(

            query=query,

            search_depth="advanced",

            max_results=5,

            include_answer=True
        )

        results = []

        for item in response.get(
            "results",
            []
        ):

            results.append({

                "title": item.get(
                    "title"
                ),

                "url": item.get(
                    "url"
                ),

                "content": item.get(
                    "content"
                )
            })

        return {

            "answer": response.get(
                "answer"
            ),

            "results": results
        }

    except Exception as e:

        return {

            "error": str(e)
        }


# ============================================================
# LANGCHAIN TOOLS
# ============================================================

@tool
def geoapify_places(
    lat: float,
    lon: float,
    category: str = "tourism.sights",
    radius: int = 5000
):
    """
    Find tourist attractions, restaurants,
    museums and other places near coordinates.
    """

    return search_places(
        lat=lat,
        lon=lon,
        category=category,
        radius=radius
    )


@tool
def weather_forecast(city: str):
    """
    Get upcoming weather forecast for a city.
    """

    return get_weather(city)


@tool
def travel_web_search(query: str):
    """
    Search the web for current travel information,
    attractions, events and recommendations.
    """

    return search_travel_info(query)


tools = [

    geoapify_places,

    weather_forecast,

    travel_web_search

]


# ============================================================
# GEMINI
# ============================================================

try:

    llm = ChatGoogleGenerativeAI(

        model="gemini-2.5-flash",

        google_api_key=google_api_key,

        temperature=0.3
    )

except Exception as e:

    st.error(
        f"Gemini initialization failed: {e}"
    )

    st.stop()


# ============================================================
# AI TRIP AGENT
# ============================================================

try:

    trip_agent = create_agent(

        model=llm,

        tools=tools,

        system_prompt="""

You are an expert AI Trip Planner.

Your responsibility is to create practical,
personalized and realistic travel itineraries.

You have access to three tools:

1. geoapify_places
   Find attractions, tourist places,
   restaurants and nearby locations.

2. weather_forecast
   Get upcoming weather information.

3. travel_web_search
   Search current travel information
   from the web.

IMPORTANT:

Use the tools whenever useful.

Consider:

- Destination
- Budget
- Number of days
- User interests
- Travel style
- Weather
- Tourist attractions
- Restaurants
- Current travel information
- Travel time
- Practical scheduling

Group nearby attractions together
whenever possible.

Consider weather when scheduling
outdoor activities.

Avoid scheduling too many places
in one day.

Keep the itinerary realistic
and budget-conscious.

Create a detailed day-wise itinerary.

For every day include:

Morning
Afternoon
Evening
Places to visit
Food recommendations
Estimated cost
Weather considerations

Also provide:

Total estimated budget
Food recommendations
Travel tips
Important current information

Do not invent current information
when it can be checked using tools.

"""
    )

except Exception as e:

    st.error(
        f"Agent initialization failed: {e}"
    )

    st.stop()


# ============================================================
# MAIN UI
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 42px;
        font-weight: 700;
        text-align: center;
        margin-bottom: 5px;
    }

    .subtitle {
        text-align: center;
        font-size: 18px;
        margin-bottom: 30px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


st.markdown(
    '<div class="main-title">✈️ AI Trip Planner</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Create personalized trips using Gemini, '
    'Geoapify, Weather and Tavily.'
    '</div>',
    unsafe_allow_html=True
)


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
    "📅 Number of Days",
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

    default=[
        "History",
        "Food"
    ]
)

travel_style = st.sidebar.selectbox(

    "🚗 Travel Style",

    [

        "Budget-friendly",
        "Comfort",
        "Luxury"

    ]
)


# ============================================================
# BUTTONS
# ============================================================

generate_button = st.sidebar.button(
    "✨ Generate Itinerary",
    use_container_width=True
)

clear_button = st.sidebar.button(
    "🗑️ Clear Conversation",
    use_container_width=True
)


# ============================================================
# CLEAR CHAT
# ============================================================

if clear_button:

    st.session_state.messages = []

    st.rerun()


# ============================================================
# GENERATE ITINERARY
# ============================================================

if generate_button:

    if not destination:

        st.warning(
            "⚠️ Please enter a destination."
        )

    elif not interests:

        st.warning(
            "⚠️ Please select at least one interest."
        )

    else:

        interest_text = ", ".join(
            interests
        )

        prompt = f"""

Plan a complete trip using these details.

Destination:
{destination}

Budget:
₹{budget}

Number of days:
{days}

Interests:
{interest_text}

Travel style:
{travel_style}

Use your available tools to research
the destination.

Create a realistic day-wise itinerary.

For every day include:

### Day X

Morning:
- Activity
- Place
- Estimated cost

Afternoon:
- Activity
- Place
- Estimated cost

Evening:
- Activity
- Place
- Estimated cost

Food:
- Recommended food/place

Weather:
- Weather consideration

Also provide:

### Total Budget

Break down the approximate cost for:

- Accommodation
- Food
- Local transportation
- Attractions
- Miscellaneous

Try to keep the trip within
the user's budget.

Also provide:

### Travel Tips

Include useful current travel
information from the tools.

"""


        st.session_state.messages = [

            {
                "role": "user",
                "content": prompt
            }

        ]


        with st.spinner(
            "🤖 AI is planning your trip..."
        ):

            try:

                response = trip_agent.invoke({

                    "messages":
                    st.session_state.messages

                })

                final_message = response[
                    "messages"
                ][-1].content


                st.session_state.messages.append({

                    "role": "assistant",

                    "content": final_message

                })


                st.success(
                    "🎉 Your itinerary is ready!"
                )

                st.markdown(
                    final_message
                )


            except Exception as e:

                st.error(
                    f"❌ Error while generating itinerary: {e}"
                )


# ============================================================
# SHOW PREVIOUS CONVERSATION
# ============================================================

if st.session_state.messages:

    for message in st.session_state.messages:

        if message["role"] == "assistant":

            continue


# ============================================================
# FOLLOW-UP CHAT
# ============================================================

st.divider()

st.subheader("💬 Modify Your Trip")

st.caption(
    "Example: Make Day 2 cheaper, "
    "add more restaurants, or replace "
    "an outdoor activity."
)


user_message = st.chat_input(
    "Ask something about your itinerary..."
)


if user_message:

    if not st.session_state.messages:

        st.warning(
            "Please generate an itinerary first."
        )

    else:

        st.session_state.messages.append({

            "role": "user",

            "content": user_message

        })

        with st.spinner(
            "🤖 Updating your itinerary..."
        ):

            try:

                response = trip_agent.invoke({

                    "messages":
                    st.session_state.messages

                })

                final_message = response[
                    "messages"
                ][-1].content


                st.session_state.messages.append({

                    "role": "assistant",

                    "content": final_message

                })


                st.markdown(
                    final_message
                )


            except Exception as e:

                st.error(
                    f"❌ Error: {str(e)}"
                )
```
