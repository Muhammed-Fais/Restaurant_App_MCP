# Restaurant Chatbot

This project is a FastAPI-based chat application that allows users to interact with a restaurant chatbot. The chatbot can browse the menu, place orders, and manage existing orders.

## Project Structure

```
.
├── app/                      # Main application logic
│   ├── __init__.py
│   ├── main.py               # FastAPI main application, agent setup
│   ├── restaurant_server.py  # MCP server with restaurant tools
│   └── db_setup.py           # SQLite database setup and population
├── data/                     # Data files
│   └── restaurant.db         # SQLite database
├── static/                   # Static files for the frontend
│   ├── index.html            # Main HTML page for the chat interface
│   ├── style.css             # CSS styles
│   └── script.js             # JavaScript for frontend logic
├── .gitignore                # Specifies intentionally untracked files that Git should ignore
└── requirements.txt          # Python package dependencies
└── README.md                 # This file
```

## Setup and Installation

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <your-repository-url>
    cd <your-project-directory>
    ```

2.  **Create a virtual environment:**
    It's highly recommended to use a virtual environment to manage project dependencies.
    ```bash
    python -m venv venv
    ```
    Activate the virtual environment:
    *   On Windows:
        ```bash
        .\venv\Scripts\activate
        ```
    *   On macOS/Linux:
        ```bash
        source venv/bin/activate
        ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up the database:**
    The application uses an SQLite database. To create and populate the database with menu items, run the following command from the project's root directory:
    ```bash
    python -m app.db_setup
    ```
    This will create a `restaurant.db` file in the `data/` directory.

## Running the Application

1.  **Start the FastAPI application:**
    Ensure your virtual environment is activated. Then, run the following command from the project's root directory:
    ```bash
    python app/main.py
    ```
    Or using Uvicorn directly for more options (like auto-reload):
    ```bash
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```

2.  **Access the application:**
    Open your web browser and navigate to `http://localhost:8000`. You should see the chat interface.

## How it Works

*   **FastAPI (`app/main.py`):** Handles HTTP requests, serves the frontend, and manages the AI agent lifecycle.
*   **MCP Server (`app/restaurant_server.py`):** Implements the tools (e.g., `browse_menu`, `place_order`) that the AI agent can use to interact with the restaurant's data (database).
*   **LangGraph/Ollama:** The AI agent logic is powered by LangGraph and a local Ollama model (e.g., `llama3.2`) to process user messages and decide which tools to use.
*   **SQLite (`data/restaurant.db`):** Stores menu items and order information.
*   **Frontend (`static/`):** A simple HTML, CSS, and JavaScript interface for users to chat with the bot.

## To-Do / Potential Enhancements
(Add any future plans or ideas here)
*   More sophisticated error handling.
*   User authentication.
*   Real-time order status updates.
*   Payment integration. 