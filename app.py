import streamlit as st
import requests

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain.agents import create_agent
from tavily import TavilyClient


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Trip Planner",
    page_icon="✈️",
    layout="wide"
)


# ============================================================
# LOAD API KEYS FROM STREAMLIT SECRETS
# ============================================================

GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
GEOAPIFY_API_KEY = st.secrets["GEOAPIFY_API_KEY"]
TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
OPENWEATHER_API_KEY = st.secrets["OPENWEATHER_API_KEY"]


# ============================================================
# GEOAPIFY - PLACES SEARCH
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
        "apiKey": GEOAPIFY_API_KEY
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
# WEATHER API
# ============================================================

def get_weather(city: str):

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
    )

    params = {

        "q": city,

        "appid": OPENWEATHER_API_KEY,

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
# TAVILY SEARCH
# ============================================================

tavily_client = TavilyClient(
    api_key=TAVILY_API_KEY
)


def search_travel_info(query: str):

    try:

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
    Get the upcoming weather forecast
    for a city.
    """

    return get_weather(city)


@tool
def travel_web_search(query: str):
    """
    Search the web for current travel
    information, attractions, events,
    recommendations and travel tips.
    """

    return search_travel_info(query)


tools = [

    geoapify_places,

    weather_forecast,

    travel_web_search

]


# ============================================================
# GEMINI MODEL
# ============================================================

llm = ChatGoogleGenerativeAI(

    model="gemini-2.5-flash",

    google_api_key=GOOGLE_API_KEY,

    temperature=0.3
)


# ============================================================
# AI TRIP PLANNER AGENT
# ============================================================

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
   restaurants and other nearby locations.

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

Avoid placing too many locations
in one day.

Group nearby attractions together
whenever possible.

Consider weather when scheduling
outdoor activities.

Keep the itinerary realistic
and budget-conscious.

Return a detailed day-wise itinerary.

For each day provide:

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

Do not invent specific current information
when it can be checked using the tools.

"""
)


# ============================================================
# SESSION MEMORY
# ============================================================

if "messages" not in st.session_state:

    st.session_state.messages = []


# ============================================================
# CUSTOM CSS
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

    .trip-card {

        padding: 20px;

        border-radius: 15px;

        border: 1px solid #ddd;

        margin-top: 20px;

    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">✈️ AI Trip Planner</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Plan personalized trips using AI, Geoapify, '
    'weather data and live web search.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("🌍 Trip Details")

    destination = st.text_input(
        "📍 Destination",
        placeholder="Example: Jaipur"
    )

    budget = st.number_input(

        "💰 Budget (INR)",

        min_value=1000,

        value=20000,

        step=1000
    )

    days = st.number_input(

        "📅 Number of Days",

        min_value=1,

        max_value=30,

        value=3,

        step=1
    )

    interests = st.multiselect(

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

    travel_style = st.selectbox(

        "🚗 Travel Style",

        [

            "Budget-friendly",

            "Comfort",

            "Luxury"

        ]
    )

    st.divider()

    generate_button = st.button(

        "✨ Generate Itinerary",

        use_container_width=True
    )

    clear_button = st.button(

        "🗑️ Clear Conversation",

        use_container_width=True
    )


# ============================================================
# CLEAR CONVERSATION
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

Provide an approximate breakdown
for:

- Accommodation
- Food
- Local transportation
- Attractions
- Miscellaneous

Keep the total within the user's
budget whenever realistically possible.

Also provide:

### Travel Tips

Include useful current travel
information obtained from your tools.

"""


        with st.spinner(
            "🤖 AI is planning your trip..."
        ):

            try:

                st.session_state.messages.append({

                    "role": "user",

                    "content": prompt

                })


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
                    f"❌ Error: {str(e)}"
                )


# ============================================================
# FOLLOW-UP CHAT
# ============================================================

st.divider()

st.subheader("💬 Modify Your Trip")

st.caption(
    "Ask the planner to modify the itinerary, "
    "for example: 'Make Day 2 cheaper' "
    "or 'Add more food recommendations'."
)


user_message = st.chat_input(
    "Ask something about your trip..."
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
