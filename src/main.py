import os
from groq import Groq
from dotenv import load_dotenv
from typing import List
from .providers.wikipedia import fetch_attractions

# Load environment variables from project root .env explicitly
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_env_path = os.path.join(_project_root, ".env")
load_dotenv(dotenv_path=_env_path, override=True)

def generate_vacation_plan(preferences: dict) -> str:
    """
    Generates a personalized vacation plan using the Groq API based on user preferences.

    Args:
        preferences: A dictionary containing user preferences such as destination,
                     duration, budget, and interests.

    Returns:
        A string containing the AI-generated vacation plan.
    """
    try:
        api_key = os.environ.get("GROQ_API_KEY")
        print(f"Debug GROQ key present: {bool(api_key)}; env path: {_env_path}")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable not set.")

        # Collect public context for grounding
        destination = preferences.get("destination", "")
        attractions = fetch_attractions(destination, limit=6)
        attractions_lines: List[str] = [
            f"- {a['name']}: {a.get('desc','').strip()}" for a in attractions if a.get('name')
        ]
        context_block = "\n".join(attractions_lines) if attractions_lines else "- No external context found"

        client = Groq(api_key=api_key)

        model_name = os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")
        try:
            temperature = float(os.environ.get("LLM_TEMPERATURE", "0.3"))
        except ValueError:
            temperature = 0.3

        system_prompt = (
            "You are WanderGenie, an expert travel agent specializing in creating "
            "personalized vacation itineraries. Your goal is to generate a detailed, "
            "day-by-day plan tailored to the user's preferences.\n\n"
            "Strictly return an HTML table only (no extra text). Columns: "
            "Day, Time (HH:MM–HH:MM), Agenda, Cost (local currency).\n"
            "Break down each day into multiple rows (one row per activity with realistic start and end times).\n"
            "Provide approximate costs per activity in the destination's local currency, using numeric values (e.g., JPY 1500).\n"
            "Do NOT include a global footer total row; totals will be computed per-day by the client.\n"
            "Apply HTML attributes/classes suitable for Bootstrap tables: <table class='table table-striped table-bordered plan-table'>.\n\n"
            "Destination context (public data, optional):\n" + context_block + "\n"
        )

        user_prompt = (
            f"Please generate a vacation plan based on the following preferences:\n"
            f"- Destination: {destination or 'not specified'}\n"
            f"- Duration: {preferences.get('duration', 'not specified')} days (build a schedule with realistic times each day)\n"
            f"- Budget: {preferences.get('budget', 'not specified')} (keep costs aligned with this level)\n"
            f"- Interests: {', '.join(preferences.get('interests', [])) if preferences.get('interests') else 'not specified'}\n\n"
            "Return only the HTML <table> as specified. No explanations, no markdown, no code fences."
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model_name,
            temperature=temperature,
            max_tokens=2048,
            top_p=1,
            stop=None,
            stream=False,
        )

        return chat_completion.choices[0].message.content

    except Exception as e:
        print(f"An error occurred: {e}")
        # Provide an HTML table fallback so the UI remains functional
        return (
            "<table class='table table-striped table-bordered plan-table'>"
            "<thead><tr><th>Day</th><th>Time</th><th>Agenda</th><th>Cost (local)</th></tr></thead>"
            "<tbody>"
            "<tr><td>Day 1</td><td>09:00–11:00</td><td>City walking tour</td><td>JPY 2500</td></tr>"
            "<tr><td>Day 1</td><td>12:00–13:30</td><td>Lunch at local restaurant</td><td>JPY 1800</td></tr>"
            "<tr><td>Day 2</td><td>10:00–12:00</td><td>Visit landmark museum</td><td>JPY 1500</td></tr>"
            "<tr><td>Day 2</td><td>14:00–16:00</td><td>Parks and gardens</td><td>JPY 0</td></tr>"
            "</tbody></table>"
        )

if __name__ == '__main__':
    # Example usage for testing
    test_preferences = {
        "destination": "Kyoto, Japan",
        "duration": 5,
        "budget": "Moderate",
        "interests": ["Culture", "Food", "Nature", "Photography"]
    }
    
    print("Generating a sample vacation plan...")
    plan = generate_vacation_plan(test_preferences)
    print("\n--- Generated Plan ---\n")
    print(plan)