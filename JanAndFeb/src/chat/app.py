"""Natural language query interface for trading data using Ollama + Gradio."""

import json
import os

import gradio as gr
import httpx
import psycopg
import pandas as pd

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://trading:trading@localhost:5432/trades")

# Database schema context for the LLM
SCHEMA_CONTEXT = """
You are a SQL expert. Generate PostgreSQL queries for an energy trading database.

Available tables:

1. trade_aggregates (main table - minute-level aggregates)
   - symbol: VARCHAR(20) - trading symbol (POWER_DE, POWER_FR, POWER_NL, GAS_NL, GAS_UK, BRENT_OIL, CARBON_EU)
   - window_start: TIMESTAMPTZ - start of 1-minute window
   - window_end: TIMESTAMPTZ - end of 1-minute window
   - vwap: NUMERIC(18,8) - Volume Weighted Average Price
   - total_volume: NUMERIC(18,8) - sum of trade volumes
   - trade_count: INTEGER - number of trades
   - max_price: NUMERIC(18,8) - highest price in window
   - min_price: NUMERIC(18,8) - lowest price in window

2. dlq_messages (dead letter queue - failed messages)
   - error_type: VARCHAR(100)
   - error_message: TEXT
   - failed_at: TIMESTAMPTZ

Rules:
- Only generate SELECT queries (no INSERT, UPDATE, DELETE)
- Use NOW() for current time comparisons
- Use INTERVAL for time ranges (e.g., INTERVAL '1 hour')
- Return ONLY the SQL query, no explanations
- Limit results to 100 rows unless specified otherwise
"""


def query_ollama(prompt: str) -> str:
    """Send a prompt to Ollama and get the response."""
    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except httpx.HTTPError as e:
        return f"Error connecting to Ollama: {e}"


def generate_sql(question: str) -> str:
    """Convert natural language question to SQL using Ollama."""
    prompt = f"""{SCHEMA_CONTEXT}

User question: {question}

Generate a SQL query to answer this question. Return ONLY the SQL, no explanations."""

    sql = query_ollama(prompt)
    # Clean up the response - remove markdown code blocks if present
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def execute_query(sql: str) -> tuple[pd.DataFrame | None, str]:
    """Execute SQL query and return results as DataFrame."""
    # Safety check - only allow SELECT
    if not sql.strip().upper().startswith("SELECT"):
        return None, "Only SELECT queries are allowed."

    try:
        with psycopg.connect(POSTGRES_DSN) as conn:
            df = pd.read_sql(sql, conn)
            return df, ""
    except Exception as e:
        return None, f"Query error: {e}"


def chat(question: str, history: list) -> tuple[str, pd.DataFrame | None]:
    """Process a natural language question and return results."""
    if not question.strip():
        return "Please enter a question.", None

    # Generate SQL
    sql = generate_sql(question)

    if sql.startswith("Error"):
        return sql, None

    # Execute query
    df, error = execute_query(sql)

    if error:
        response = f"**Generated SQL:**\n```sql\n{sql}\n```\n\n**Error:** {error}"
        return response, None

    if df is None or df.empty:
        response = f"**Generated SQL:**\n```sql\n{sql}\n```\n\nNo results found."
        return response, None

    response = f"**Generated SQL:**\n```sql\n{sql}\n```\n\n**Results:** {len(df)} rows"
    return response, df


# Example questions for the UI
EXAMPLES = [
    "What is the current VWAP for POWER_DE?",
    "Show me the top 5 symbols by volume in the last hour",
    "What was the price range for GAS_NL today?",
    "How many trades happened in the last 30 minutes?",
    "Which symbol has the highest volatility?",
    "Show me hourly volume for CARBON_EU",
]


def create_ui() -> gr.Blocks:
    """Create the Gradio interface."""
    with gr.Blocks(title="Trading Data Chat", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Chat with Trading Data")
        gr.Markdown("Ask questions about energy trading data in natural language.")

        with gr.Row():
            with gr.Column(scale=2):
                question = gr.Textbox(
                    label="Your Question",
                    placeholder="e.g., What is the VWAP for POWER_DE in the last hour?",
                    lines=2,
                )
                submit_btn = gr.Button("Ask", variant="primary")

            with gr.Column(scale=1):
                gr.Markdown("**Example Questions:**")
                for ex in EXAMPLES:
                    gr.Markdown(f"- {ex}")

        response = gr.Markdown(label="Response")
        results = gr.Dataframe(label="Results", interactive=False)

        submit_btn.click(
            fn=lambda q: chat(q, []),
            inputs=[question],
            outputs=[response, results],
        )
        question.submit(
            fn=lambda q: chat(q, []),
            inputs=[question],
            outputs=[response, results],
        )

    return demo


def main() -> None:
    """Run the Gradio app."""
    demo = create_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
