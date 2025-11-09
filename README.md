# WanderGenie: The Autonomous AI Vacation Planner

**WanderGenie** is a proof-of-concept for a B2B SaaS platform that automates corporate vacation planning. It functions as an intelligent agent that analyzes employee preferences (budget, interests, travel style), recommends personalized destinations, and generates detailed daily itineraries.

## Features

- **AI-Powered Itineraries:** Leverages the Llama 3 language model via the Groq API to generate creative and personalized travel plans.
- **FastAPI Backend:** A high-performance backend serves the application and provides a RESTful API.
- **Simple Frontend:** A clean, responsive user interface built with HTML and Bootstrap.
- **Easy Setup:** Uses `uv` for a modern and fast dependency management workflow.

## Project Structure

```
01-WanderGenie/
├── .env
├── .env.example
├── README.md
├── app.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   └── main.py
├── static/
└── templates/
    └── index.html
```

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd 01-WanderGenie
    ```

2.  **Create a virtual environment:**
    ```bash
    uv venv
    ```

3.  **Activate the virtual environment:**
    - On Windows:
        ```bash
        .venv\Scripts\activate
        ```
    - On macOS/Linux:
        ```bash
        source .venv/bin/activate
        ```

4.  **Install the dependencies:**
    ```bash
    uv pip install -r requirements.txt
    ```

5.  **Set up your environment variables:**
    - Create a `.env` file by copying the `.env.example` file.
    - Add your Groq API key to the `.env` file:
        ```
        GROQ_API_KEY="YOUR_API_KEY_HERE"
        ```

## How to Run the Application

1.  **Start the FastAPI server:**
    ```bash
    uvicorn app:app --reload
    ```

2.  **Open your browser:**
    Navigate to `http://127.0.0.1:8000` to use the web interface.

## API Usage

You can also interact with the API directly. The API documentation is available at `http://127.0.0.1:8000/docs`.

### Example `curl` Request

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/api/plan' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "destination": "Paris, France",
  "duration": 3,
  "budget": "Luxury",
  "interests": [
    "Art",
    "History",
    "Fine Dining"
  ]
}'
```