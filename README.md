# ✈️ AI Trip Planner

An AI-powered travel planning app built with Streamlit and LangChain. Give it a destination, budget, and number of days, and it generates a realistic, day-wise itinerary using live web search, weather, and places data — then lets you refine the plan through follow-up chat.

## Features

- **Day-wise itineraries** — morning, afternoon, evening activities with estimated costs, food suggestions, and weather for each day
- **Live data tools**
  - **Places** — tourist attractions near the destination via Geoapify
  - **Weather** — forecast data via OpenWeather
  - **Search** — current travel information via Tavily
- **Budget summary** — cost breakdown by category (accommodation, food, transport, attractions, other)
- **Conversational refinement** — chat with the planner after the first itinerary to tweak it (e.g. "make Day 2 cheaper", "replace a restaurant")
- **Structured rendering** — the model's Markdown output is parsed and displayed as metrics, expandable day-by-day sections, and tables rather than one long text block

## Tech Stack

- [Streamlit](https://streamlit.io/) — web UI
- [LangChain](https://www.langchain.com/) (`langchain-google-genai`, `langchain.agents`) — agent orchestration
- **Google Gemini** — the underlying LLM
- **Tavily** — web search tool
- **Geoapify** — places/attractions data
- **OpenWeather** — weather forecasts

## Prerequisites

You'll need API keys for:

| Service | Used for | Get a key |
|---|---|---|
| Google Gemini | LLM / agent reasoning | [Google AI Studio](https://aistudio.google.com/) |
| Geoapify | Tourist attractions & places | [Geoapify](https://www.geoapify.com/) |
| Tavily | Web search | [Tavily](https://tavily.com/) |
| OpenWeather | Weather forecasts | [OpenWeatherMap](https://openweathermap.org/api) |

## Installation

```bash
pip install streamlit requests tavily-python langchain-google-genai langchain
```

## Usage

1. Run the app:

   ```bash
   streamlit run app.py
   ```

2. In the sidebar, enter your four API keys and click **🔌 Connect APIs**.
3. Fill in trip details — destination, budget (INR), and number of days.
4. Click **✨ Generate Trip** to create the itinerary.
5. Use the **💬 Modify Your Trip** chat box to ask for changes to the plan.
6. Click **🗑️ Clear Trip** to reset and start over.

## How It Works

1. The app initializes a LangChain agent (`create_agent`) backed by Gemini, with three tools attached: `places_tool`, `weather_tool`, and `search_tool`.
2. A system prompt instructs the agent to act as a professional trip planner and to always return output in a fixed Markdown structure (trip summary, day-by-day plan, budget table, travel tips).
3. On **Generate Trip**, the app sends a prompt with the destination, budget, and day count, and the agent calls its tools as needed to gather live data before producing the itinerary.
4. The raw Markdown response is split by top-level (`# `) sections and rendered with dedicated Streamlit widgets:
   - Trip Summary → metric cards
   - Each Day → a collapsible expander
   - Budget Summary / Travel Tips → rendered Markdown
5. Follow-up messages are appended to the running conversation (`st.session_state.messages`) so the agent has full context for edits.

## Project Structure

```
.
├── app.py          # Main Streamlit application
└── README.md
```

## Notes

- All four API keys must be entered before the app becomes usable — trip planning is blocked until `Connect APIs` succeeds.
- The itinerary generation keeps the total estimated cost within the given budget where possible, but this isn't strictly enforced.
- Currency is assumed to be INR (₹) throughout the prompts and UI.

## Possible Improvements

- Persist trip history across sessions (currently resets on refresh)
- Add input validation / friendlier error messages for invalid API keys
- Support multiple currencies
- Cache tool results to reduce redundant API calls during follow-up edits
