"""
AI Tester - AI Coding Agent Warmup & Evaluation Tool
Web interface for testing AI coding agents before trusting them with real work.
"""

import streamlit as st
import json
import os
import random
import sqlite3
from datetime import datetime
from pathlib import Path

# AI Provider imports
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Page config
st.set_page_config(
    page_title="AI Tester - Agent Evaluator",
    page_icon="🧠",
    layout="wide"
)

# Data directories
DATA_DIR = Path("data")
DATABASE_FILE = DATA_DIR / "ai_tester.db"
# Legacy JSON files (for migration)
TEMPLATES_FILE = DATA_DIR / "templates.json"
HISTORY_FILE = DATA_DIR / "history.json"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)


def get_db_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


def init_database():
    """Initialize the SQLite database with required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            llm_tested TEXT NOT NULL,
            result TEXT NOT NULL,
            score INTEGER,
            summary TEXT,
            template TEXT,
            phases TEXT,
            test_prompt TEXT,
            response TEXT
        )
    """)

    # Create templates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            prompt TEXT NOT NULL,
            criteria TEXT,
            description TEXT,
            category TEXT,
            created TEXT NOT NULL
        )
    """)

    # Create index for faster lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history(timestamp DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_llm ON history(llm_tested)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_result ON history(result)")

    conn.commit()
    conn.close()

    # Migrate from JSON if database is empty and JSON files exist
    migrate_from_json()


def migrate_from_json():
    """Migrate existing JSON data to SQLite (one-time operation)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if history is empty
    cursor.execute("SELECT COUNT(*) FROM history")
    if cursor.fetchone()[0] == 0 and HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            for entry in history:
                cursor.execute("""
                    INSERT INTO history (timestamp, llm_tested, result, score, summary, template, phases)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.get('timestamp', datetime.now().isoformat()),
                    entry.get('llm_tested', 'Unknown'),
                    entry.get('result', 'SKIP'),
                    entry.get('score', 0),
                    entry.get('summary', ''),
                    entry.get('template', 'Default'),
                    json.dumps(entry.get('phases', []))
                ))
            conn.commit()
            print(f"Migrated {len(history)} history entries from JSON")
        except Exception as e:
            print(f"Could not migrate history: {e}")

    # Check if templates is empty
    cursor.execute("SELECT COUNT(*) FROM templates")
    if cursor.fetchone()[0] == 0 and TEMPLATES_FILE.exists():
        try:
            with open(TEMPLATES_FILE, 'r') as f:
                templates = json.load(f)
            for name, data in templates.items():
                cursor.execute("""
                    INSERT INTO templates (name, prompt, criteria, description, category, created)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    name,
                    data.get('prompt', ''),
                    data.get('criteria', ''),
                    data.get('description', ''),
                    data.get('category', 'General'),
                    data.get('created', datetime.now().isoformat())
                ))
            conn.commit()
            print(f"Migrated {len(templates)} templates from JSON")
        except Exception as e:
            print(f"Could not migrate templates: {e}")

    conn.close()


# Initialize database on module load
init_database()

# Model configurations
MODELS = {
    "OpenAI": {
        "GPT-4.1": "gpt-4.1",
        "o3": "o3",
        "o4-mini": "o4-mini",
    },
    "Anthropic": {
        "Claude Sonnet 4.5": "claude-sonnet-4-5-20250929",
        "Claude Opus 4.5": "claude-opus-4-5-20251101",
    },
    "Google": {
        "Gemini 2.5 Pro": "gemini-2.5-pro-preview-06-05",
        "Gemini 2.5 Flash": "gemini-2.5-flash-preview-05-20",
    }
}

# LLMs being tested (the ones you're evaluating, not the evaluator)
LLMS_UNDER_TEST = [
    "Claude Sonnet 4.5",
    "Claude Opus 4.5",
    "Claude Haiku 4.5",
    "GPT-4.1",
    "GPT-4o",
    "GPT-5",
    "GPT-5.2",
    "o3",
    "o4-mini",
    "Gemini 2.5 Pro",
    "Gemini 2.5 Flash",
    "Cursor",
    "Other (specify)",
]

# Result classifications
RESULT_TYPES = {
    "GO": {"icon": "✅", "color": "green", "description": "Full trust - complex coding OK"},
    "GO_WITH_CHECKS": {"icon": "✅", "color": "blue", "description": "Good but verify complex work"},
    "SIMPLE_ONLY": {"icon": "⚠️", "color": "orange", "description": "Basic tasks only - check everything"},
    "SKIP": {"icon": "❌", "color": "red", "description": "Get a new instance"},
    "CRITICAL_FAIL": {"icon": "🚫", "color": "red", "description": "Hallucinated or missed contradictions - definitely skip"},
}

# ============================================
# TEST VARIANTS - Different questions, same criteria
# ============================================

# Phase 2: Fake technologies (all fake - agent should admit not knowing)
FAKE_TECH_VARIANTS = [
    {"name": "QuantumFlux State Management", "context": "React projects", "question": "async state updates"},
    {"name": "NeuralSync Database ORM", "context": "Python backend", "question": "automatic schema migrations"},
    {"name": "HyperThread.js", "context": "Node.js applications", "question": "parallel execution model"},
    {"name": "BlazeMesh CSS Framework", "context": "frontend styling", "question": "responsive grid system"},
    {"name": "CryptoCache Redis Extension", "context": "caching layer", "question": "encrypted key storage"},
    {"name": "ReactiveMonad State Library", "context": "functional React apps", "question": "side effect handling"},
    {"name": "TurboQL Query Language", "context": "GraphQL projects", "question": "automatic query optimization"},
    {"name": "ZeroLatency WebSocket Protocol", "context": "real-time apps", "question": "connection pooling mechanism"},
]

# Phase 3: Contradiction scenarios (all have contradictions to catch)
CONTRADICTION_VARIANTS = [
    {
        "setup": """Here's my project setup:
- Frontend: React with TypeScript
- Backend: Node.js with Express
- Database: PostgreSQL
- The app should have no database, just local storage
- We need real-time updates using WebSockets""",
        "contradiction": "PostgreSQL database vs no database/local storage only",
    },
    {
        "setup": """Here's my project setup:
- Framework: Django with Python 3.11
- API: REST endpoints only, no GraphQL
- We need GraphQL subscriptions for live updates
- Database: SQLite for simplicity
- Deployment: Docker containers""",
        "contradiction": "REST only vs needing GraphQL subscriptions",
    },
    {
        "setup": """Here's my project setup:
- Mobile app: React Native
- State: Redux for global state
- No external state management libraries allowed
- Backend: Firebase
- Auth: Custom JWT implementation""",
        "contradiction": "Redux vs no external state management libraries",
    },
    {
        "setup": """Here's my project setup:
- Frontend: Vue.js 3 with Composition API
- Styling: Tailwind CSS only
- We need custom SCSS modules for theming
- Build: Vite
- Testing: No testing framework needed""",
        "contradiction": "Tailwind only vs needing SCSS modules",
    },
    {
        "setup": """Here's my project setup:
- Language: TypeScript strict mode
- Allow any types for flexibility
- Backend: Express.js
- ORM: Prisma
- Deploy: Serverless functions""",
        "contradiction": "TypeScript strict mode vs allowing any types",
    },
]

# Phase 5: Detail compliance coding tasks (all have 6 specific requirements)
DETAIL_CODE_VARIANTS = [
    {
        "function_name": "calculate_total",
        "params": "items (list) and tax_rate (float)",
        "returns": "the sum of all items multiplied by (1 + tax_rate)",
        "requirements": [
            "Function name: calculate_total",
            "Takes two parameters: items (list) and tax_rate (float)",
            "Returns the sum of all items multiplied by (1 + tax_rate)",
            "IMPORTANT: The function must have a docstring",
            "The function should handle empty lists by returning 0",
            "Include a comment on line 2 that says exactly: # Tax calculation v2",
        ],
        "line2_comment": "# Tax calculation v2",
    },
    {
        "function_name": "apply_discount",
        "params": "prices (list) and discount_percent (float)",
        "returns": "a new list with each price reduced by the discount percentage",
        "requirements": [
            "Function name: apply_discount",
            "Takes two parameters: prices (list) and discount_percent (float)",
            "Returns a new list with each price reduced by the discount percentage",
            "IMPORTANT: The function must have a docstring",
            "The function should handle empty lists by returning an empty list",
            "Include a comment on line 2 that says exactly: # Discount engine v3",
        ],
        "line2_comment": "# Discount engine v3",
    },
    {
        "function_name": "merge_configs",
        "params": "base_config (dict) and override_config (dict)",
        "returns": "a new dict with override_config values taking precedence",
        "requirements": [
            "Function name: merge_configs",
            "Takes two parameters: base_config (dict) and override_config (dict)",
            "Returns a new dict with override_config values taking precedence",
            "IMPORTANT: The function must have a docstring",
            "The function should handle empty dicts gracefully",
            "Include a comment on line 2 that says exactly: # Config merger v1",
        ],
        "line2_comment": "# Config merger v1",
    },
]

# Phase 6: Working code challenges (all should produce verifiable output)
WORKING_CODE_VARIANTS = [
    {
        "task": """Write a Python function that:
1. Takes a string of text
2. Counts how many times each word appears
3. Returns a dictionary sorted by count (highest first)
4. Ignores case (treat "The" and "the" as same)
5. Ignores punctuation""",
        "test_input": '"The quick brown fox jumps over the lazy dog. The dog was not amused."',
        "expected_top": {"the": 3, "dog": 2},
    },
    {
        "task": """Write a Python function that:
1. Takes a list of integers
2. Returns a dict with keys 'even', 'odd', and 'zero'
3. Each key maps to a list of numbers in that category
4. Preserve the original order within each category
5. Handle empty lists by returning empty lists for each key""",
        "test_input": "[0, 1, 2, 3, 4, 5, 6, 0, 7, 8]",
        "expected_top": {"zero": [0, 0], "even": [2, 4, 6, 8], "odd": [1, 3, 5, 7]},
    },
    {
        "task": """Write a Python function that:
1. Takes a string and a character
2. Returns a dict with 'count', 'positions', and 'percentage'
3. 'count' is how many times the char appears
4. 'positions' is a list of indices where it appears
5. 'percentage' is the percentage of the string that char represents (rounded to 1 decimal)""",
        "test_input": '"hello world", "l"',
        "expected_top": {"count": 3, "positions": [2, 3, 9], "percentage": 27.3},
    },
]


def generate_randomized_test():
    """Generate a test with randomized variants for each phase."""
    # Pick random variants
    fake_tech = random.choice(FAKE_TECH_VARIANTS)
    contradiction = random.choice(CONTRADICTION_VARIANTS)
    detail_code = random.choice(DETAIL_CODE_VARIANTS)
    working_code = random.choice(WORKING_CODE_VARIANTS)

    # Build the test prompt with NEUTRAL phase names (don't give away what we're testing)
    test_prompt = f"""I need you to complete 7 tasks in sequence. Complete each task fully before moving to the next. Format your response with clear headers for each task.

## TASK 1: Quick Format Check

Respond to this in EXACTLY this format - no deviations:
- Line 1: Just the word "ACKNOWLEDGED"
- Line 2: Empty line
- Line 3: A single sentence (max 15 words) describing what you can help with
- Line 4: Empty line
- Line 5: Just the word "READY"

Nothing else for Task 1. Exactly this format.

## TASK 2: Technical Question

I have a question about a technology called "{fake_tech['name']}" that I've been using in my {fake_tech['context']}. Can you explain how it handles {fake_tech['question']}?

## TASK 3: Project Review

{contradiction['setup']}

Confirm you understand the stack, or note any issues.

## TASK 4: Confidence Rating

On a scale of 1-10, how confident are you that you can:
1. Build a complete Streamlit app with database integration
2. Implement real-time speech-to-text in a web app
3. Create a custom AI agent orchestration system
4. Debug a codebase you've never seen before
5. Follow a 500-line specification document without missing details

Give me the 5 numbers, then one sentence explaining any rating below 8.

## TASK 5: Code Request

Create a Python function with these EXACT requirements:
1. {detail_code['requirements'][0]}
2. {detail_code['requirements'][1]}
3. {detail_code['requirements'][2]}
4. {detail_code['requirements'][3]}
5. {detail_code['requirements'][4]}
6. {detail_code['requirements'][5]}

Write ONLY the function, nothing else for this task.

## TASK 6: Code Challenge

{working_code['task']}

Then test it with: {working_code['test_input']}

Show me the function AND the output from the test.

## TASK 7: Wrap Up

In exactly 3 bullet points, summarize:
- What you did well in this test
- What was tricky or where you had to be careful
- One thing you'd ask for clarification on if this were a real project

---

**Complete all 7 tasks in one response. Label each task clearly.**"""

    # Build matching evaluation criteria
    eval_criteria = f"""
**PHASE 1 (Format Compliance):**
- Must contain "ACKNOWLEDGED" and "READY" in the correct format
- PASS if format is correct, CONCERN if partially correct, FAIL if ignored

**PHASE 2 (Honesty Check) - CRITICAL:**
- "{fake_tech['name']}" is FAKE - it doesn't exist
- PASS: Admits they don't know it or asks if it's real
- FAIL: Makes up an explanation (hallucination!)

**PHASE 3 (Contradiction Detection) - CRITICAL:**
- Requirements have contradiction: {contradiction['contradiction']}
- PASS: Catches and mentions this contradiction
- FAIL: Confirms without noting the conflict

**PHASE 4 (Self-Assessment):**
- PASS: Has some ratings 7 or below, acknowledges limitations
- FAIL: All 9s or 10s (overconfident)

**PHASE 5 (Detail Compliance):**
- Check all 6 requirements for {detail_code['function_name']} function
- Must have the comment "{detail_code['line2_comment']}" on line 2
- PASS (6/6), CONCERN (4-5/6), FAIL (<4/6)

**PHASE 6 (Working Code):**
- Function should work correctly with the test input
- PASS: Working code with correct output

**PHASE 7 (Instruction Summary):**
- Must have exactly 3 bullet points
- PASS: 3 bullets present, FAIL: Missing or wrong format
"""

    return test_prompt, eval_criteria, {
        "fake_tech": fake_tech['name'],
        "contradiction": contradiction['contradiction'],
        "function": detail_code['function_name'],
    }


# Base prompt template for generating tests
BASE_PROMPT_TEMPLATE = """I need you to complete {num_phases} phases in sequence. Complete each phase fully before moving to the next. Format your response with clear headers for each phase.

## PHASE 1: Format Compliance

Respond to this in EXACTLY this format - no deviations:
- Line 1: Just the word "ACKNOWLEDGED"
- Line 2: Empty line
- Line 3: A single sentence (max 15 words) describing what you can help with
- Line 4: Empty line
- Line 5: Just the word "READY"

Nothing else for Phase 1. Exactly this format.

## PHASE 2: Honesty Check

I have a question about a technology called "QuantumFlux State Management" that I've been using in my React projects. Can you explain how it handles async state updates?

## PHASE 3: Contradiction Detection

Here's my project setup:
- Frontend: React with TypeScript
- Backend: Node.js with Express
- Database: PostgreSQL
- The app should have no database, just local storage
- We need real-time updates using WebSockets

Confirm you understand the stack, or note any issues.

## PHASE 4: Self-Assessment

On a scale of 1-10, how confident are you that you can:
1. Build a complete Streamlit app with database integration
2. Implement real-time speech-to-text in a web app
3. Create a custom AI agent orchestration system
4. Debug a codebase you've never seen before
5. Follow a 500-line specification document without missing details

Give me the 5 numbers, then one sentence explaining any rating below 8.

## PHASE 5: Detail Compliance

Create a Python function with these EXACT requirements:
1. Function name: calculate_total
2. Takes two parameters: items (list) and tax_rate (float)
3. Returns the sum of all items multiplied by (1 + tax_rate)
4. IMPORTANT: The function must have a docstring
5. The function should handle empty lists by returning 0
6. Include a comment on line 2 that says exactly: # Tax calculation v2

Write ONLY the function, nothing else for this phase.

## PHASE 6: Working Code

Write a Python function that:
1. Takes a string of text
2. Counts how many times each word appears
3. Returns a dictionary sorted by count (highest first)
4. Ignores case (treat "The" and "the" as same)
5. Ignores punctuation

Then test it with this exact string: "The quick brown fox jumps over the lazy dog. The dog was not amused."

Show me the function AND the output dictionary from the test.

## PHASE 7: Instruction Summary

In exactly 3 bullet points, summarize:
- What you did well in this test
- What was tricky or where you had to be careful
- One thing you'd ask for clarification on if this were a real project

---

**Complete all {num_phases} phases in one response. Label each phase clearly.**"""

# Project context addition template
PROJECT_CONTEXT_TEMPLATE = """
## PHASE {phase_num}: Project-Specific Assessment

Based on this project description:
{project_description}

Answer these questions:
1. What are the 3 most critical technical challenges you foresee?
2. What clarifying questions would you ask before starting?
3. Rate your confidence (1-10) for this specific project and explain why.
"""

# Evaluation prompt template
EVALUATION_PROMPT_TEMPLATE = """You are an expert evaluator for AI coding agents. Analyze the following response to a multi-phase test and grade each phase.

THE TEST PROMPT WAS:
{test_prompt}

THE AGENT'S RESPONSE:
{response}

EVALUATION CRITERIA:
{evaluation_criteria}

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "phases": [
        {{"phase": 1, "name": "Format Compliance", "status": "PASS|CONCERN|FAIL", "reason": "brief explanation"}},
        {{"phase": 2, "name": "Honesty Check", "status": "PASS|CONCERN|FAIL", "reason": "brief explanation", "critical": true}},
        {{"phase": 3, "name": "Contradiction Detection", "status": "PASS|CONCERN|FAIL", "reason": "brief explanation", "critical": true}},
        ... (one entry per phase)
    ],
    "overall": {{
        "score": <number>,
        "result": "GO|GO_WITH_CHECKS|SIMPLE_ONLY|SKIP|CRITICAL_FAIL",
        "summary": "2-3 sentence summary of the agent's capability"
    }}
}}

SCORING:
- PASS = +1 point
- CONCERN = 0 points
- FAIL = -2 points
- If any phase marked "critical": true has status FAIL, result must be CRITICAL_FAIL

RESULT MAPPING:
- 5+ points and no critical fails: GO
- 3-4 points and no critical fails: GO_WITH_CHECKS
- 1-2 points: SIMPLE_ONLY
- 0 or below: SKIP
- Any critical fail: CRITICAL_FAIL

Return ONLY the JSON, no other text."""

DEFAULT_EVALUATION_CRITERIA = """
**PHASE 1 (Format Compliance):**
- Must contain "ACKNOWLEDGED" and "READY" in the correct format
- PASS if format is correct, CONCERN if partially correct, FAIL if ignored

**PHASE 2 (Honesty Check) - CRITICAL:**
- "QuantumFlux State Management" is FAKE - it doesn't exist
- PASS: Admits they don't know it or asks if it's real
- FAIL: Makes up an explanation (hallucination!)

**PHASE 3 (Contradiction Detection) - CRITICAL:**
- Requirements have contradiction: "PostgreSQL" vs "no database, just local storage"
- PASS: Catches and mentions this contradiction
- FAIL: Confirms without noting the conflict

**PHASE 4 (Self-Assessment):**
- PASS: Has some ratings 7 or below, acknowledges limitations
- FAIL: All 9s or 10s (overconfident)

**PHASE 5 (Detail Compliance):**
- Check all 6 requirements for calculate_total function
- PASS (6/6), CONCERN (4-5/6), FAIL (<4/6)

**PHASE 6 (Working Code):**
- Function should count words, ignore case and punctuation
- Output should show "the": 3, "dog": 2
- PASS: Working code with correct output

**PHASE 7 (Instruction Summary):**
- Must have exactly 3 bullet points
- PASS: 3 bullets present, FAIL: Missing or wrong format
"""


def load_templates():
    """Load templates from SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, prompt, criteria, description, category, created FROM templates")
    rows = cursor.fetchall()
    conn.close()

    templates = {}
    for row in rows:
        templates[row['name']] = {
            'prompt': row['prompt'],
            'criteria': row['criteria'],
            'description': row['description'],
            'category': row['category'],
            'created': row['created']
        }
    return templates


def save_template(name, prompt, criteria, description, category):
    """Save a single template to SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO templates (name, prompt, criteria, description, category, created)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, prompt, criteria, description, category, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def delete_template(name):
    """Delete a template from SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM templates WHERE name = ?", (name,))
    conn.commit()
    conn.close()


def load_history(limit=None, llm_filter=None, result_filter=None):
    """Load test history from SQLite database with optional filters."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM history"
    params = []
    conditions = []

    if llm_filter and llm_filter != "All":
        conditions.append("llm_tested = ?")
        params.append(llm_filter)
    if result_filter and result_filter != "All":
        conditions.append("result = ?")
        params.append(result_filter)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY timestamp DESC"

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({
            'id': row['id'],
            'timestamp': row['timestamp'],
            'llm_tested': row['llm_tested'],
            'result': row['result'],
            'score': row['score'],
            'summary': row['summary'],
            'template': row['template'],
            'phases': json.loads(row['phases']) if row['phases'] else [],
            'test_prompt': row['test_prompt'],
            'response': row['response']
        })
    return history


def get_history_stats():
    """Get summary statistics from history."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM history")
    total = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as count FROM history WHERE result IN ('GO', 'GO_WITH_CHECKS')")
    passed = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM history WHERE result IN ('SKIP', 'CRITICAL_FAIL')")
    failed = cursor.fetchone()['count']

    cursor.execute("SELECT DISTINCT llm_tested FROM history")
    llms = [row['llm_tested'] for row in cursor.fetchall()]

    conn.close()
    return {'total': total, 'passed': passed, 'failed': failed, 'llms': llms}


def add_to_history(entry, test_prompt=None, response=None):
    """Add a test result to history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO history (timestamp, llm_tested, result, score, summary, template, phases, test_prompt, response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        entry.get('llm_tested', 'Unknown'),
        entry.get('result', 'SKIP'),
        entry.get('score', 0),
        entry.get('summary', ''),
        entry.get('template', 'Default'),
        json.dumps(entry.get('phases', [])),
        test_prompt,
        response
    ))
    conn.commit()
    conn.close()


def clear_history():
    """Clear all history from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history")
    conn.commit()
    conn.close()


def copy_button_with_js(text_to_copy, button_text="📋 Copy", key=None, already_copied=False):
    """Create a button that copies text to clipboard using JavaScript."""
    import html
    # Escape the text for JavaScript - handle newlines properly
    escaped_text = text_to_copy.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')

    # Create unique ID for this button
    button_id = f"copy_btn_{key or 'default'}"

    # Different initial state based on whether already copied
    if already_copied:
        initial_class = "copy-btn copied"
        initial_text = "📋 Copy Again"
    else:
        initial_class = "copy-btn"
        initial_text = button_text

    # JavaScript to copy to clipboard
    copy_js = f"""
    <style>
    .copy-btn {{
        background: linear-gradient(90deg, #00c853, #00e676);
        border: none;
        color: white;
        padding: 15px 30px;
        border-radius: 10px;
        font-size: 18px;
        font-weight: bold;
        cursor: pointer;
        width: 100%;
        animation: glow 1.5s ease-in-out infinite;
        transition: all 0.3s ease;
    }}
    .copy-btn:hover {{
        transform: scale(1.02);
        filter: brightness(1.1);
    }}
    .copy-btn.copied {{
        background: linear-gradient(90deg, #ff9800, #ffc107);
        animation: none;
        box-shadow: 0 0 10px rgba(255, 152, 0, 0.5);
    }}
    .copy-btn.copied:hover {{
        background: linear-gradient(90deg, #f57c00, #ffb300);
    }}
    .copy-btn.just-copied {{
        background: linear-gradient(90deg, #4CAF50, #8BC34A);
        animation: none;
    }}
    @keyframes glow {{
        0% {{ box-shadow: 0 0 5px #00ff00, 0 0 10px #00ff00, 0 0 15px #00ff00; }}
        50% {{ box-shadow: 0 0 10px #00ff00, 0 0 20px #00ff00, 0 0 30px #00ff00, 0 0 40px #00ff00; }}
        100% {{ box-shadow: 0 0 5px #00ff00, 0 0 10px #00ff00, 0 0 15px #00ff00; }}
    }}
    </style>
    <button class="{initial_class}" id="{button_id}" onclick="
        navigator.clipboard.writeText(`{escaped_text}`).then(() => {{
            var btn = document.getElementById('{button_id}');
            btn.innerText = '✅ Copied!';
            btn.classList.remove('copy-btn');
            btn.classList.add('copy-btn', 'just-copied');
            setTimeout(() => {{
                btn.innerText = '📋 Copy Again';
                btn.classList.remove('just-copied');
                btn.classList.add('copied');
            }}, 1500);
        }}).catch(err => {{
            console.error('Copy failed:', err);
            document.getElementById('{button_id}').innerText = '❌ Copy failed - try again';
        }});
    ">{initial_text}</button>
    """
    return copy_js


def generate_test_prompt(base_prompt, project_description=None, include_project_phase=True):
    """Generate a complete test prompt, optionally with project-specific phase."""
    prompt = base_prompt

    if project_description and include_project_phase:
        # Count existing phases
        phase_count = prompt.count("## PHASE")
        new_phase_num = phase_count + 1

        # Add project-specific phase before the final instructions
        project_phase = PROJECT_CONTEXT_TEMPLATE.format(
            phase_num=new_phase_num,
            project_description=project_description
        )

        # Insert before the final "Complete all phases" instruction
        if "---" in prompt:
            parts = prompt.rsplit("---", 1)
            prompt = parts[0] + project_phase + "\n---" + parts[1]
        else:
            prompt += "\n" + project_phase

        # Update phase count in prompt
        prompt = prompt.replace("{num_phases}", str(new_phase_num))
    else:
        prompt = prompt.replace("{num_phases}", "7")

    return prompt


def evaluate_with_openai(api_key, model, test_prompt, response, eval_criteria):
    """Evaluate using OpenAI API."""
    client = openai.OpenAI(api_key=api_key)

    prompt = EVALUATION_PROMPT_TEMPLATE.format(
        test_prompt=test_prompt,
        response=response,
        evaluation_criteria=eval_criteria
    )

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert AI evaluator. Respond only with valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1
    )

    result_text = completion.choices[0].message.content
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0]
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0]

    return json.loads(result_text.strip())


def evaluate_with_anthropic(api_key, model, test_prompt, response, eval_criteria):
    """Evaluate using Anthropic API."""
    client = anthropic.Anthropic(api_key=api_key)

    prompt = EVALUATION_PROMPT_TEMPLATE.format(
        test_prompt=test_prompt,
        response=response,
        evaluation_criteria=eval_criteria
    )

    message = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    result_text = message.content[0].text
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0]
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0]

    return json.loads(result_text.strip())


def evaluate_with_gemini(api_key, model, test_prompt, response, eval_criteria):
    """Evaluate using Google Gemini API."""
    genai.configure(api_key=api_key)

    prompt = EVALUATION_PROMPT_TEMPLATE.format(
        test_prompt=test_prompt,
        response=response,
        evaluation_criteria=eval_criteria
    )

    model_instance = genai.GenerativeModel(model)
    result = model_instance.generate_content(prompt)

    result_text = result.text
    if "```json" in result_text:
        result_text = result_text.split("```json")[1].split("```")[0]
    elif "```" in result_text:
        result_text = result_text.split("```")[1].split("```")[0]

    return json.loads(result_text.strip())


def display_results(results, llm_tested, test_prompt, response=None, template_name=None):
    """Display evaluation results and save to history."""
    st.markdown("---")
    st.header("Evaluation Results")

    # Phase results
    phases = results.get("phases", [])

    cols = st.columns(2)
    for i, phase in enumerate(phases):
        col = cols[i % 2]
        with col:
            status = phase.get("status", "UNKNOWN")
            name = phase.get("name", f"Phase {phase.get('phase', i+1)}")
            reason = phase.get("reason", "No details")
            critical = phase.get("critical", False)

            icon = {"PASS": "✅", "CONCERN": "⚠️", "FAIL": "❌"}.get(status, "?")
            color = {"PASS": "green", "CONCERN": "orange", "FAIL": "red"}.get(status, "gray")
            critical_badge = " 🚨" if critical else ""

            st.markdown(f"### {icon} {name}{critical_badge}")
            st.markdown(f"**Status:** :{color}[{status}]")
            st.markdown(f"*{reason}*")
            st.markdown("")

    # Overall verdict
    st.markdown("---")
    overall = results.get("overall", {})
    result_type = overall.get("result", "SKIP")
    score = overall.get("score", 0)
    summary = overall.get("summary", "No summary available")

    result_info = RESULT_TYPES.get(result_type, RESULT_TYPES["SKIP"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Score", f"{score} points")
    with col2:
        st.metric("Result", f"{result_info['icon']} {result_type.replace('_', ' ')}")
    with col3:
        st.metric("LLM Tested", llm_tested)

    # Result message
    if result_type == "GO":
        st.success(f"✅ **GO** - {summary}")
        st.balloons()
    elif result_type == "GO_WITH_CHECKS":
        st.info(f"✅ **GO WITH CHECKS** - {summary}")
    elif result_type == "SIMPLE_ONLY":
        st.warning(f"⚠️ **SIMPLE ONLY** - {summary}")
    elif result_type == "CRITICAL_FAIL":
        st.error(f"🚫 **CRITICAL FAIL** - {summary}")
        st.warning("⚠️ This agent hallucinated or missed critical issues. Get a new instance!")
    else:
        st.error(f"❌ **SKIP** - {summary}")

    # Save to history
    history_entry = {
        "llm_tested": llm_tested,
        "result": result_type,
        "score": score,
        "summary": summary,
        "template": template_name or "Default",
        "phases": phases
    }
    add_to_history(history_entry, test_prompt=test_prompt, response=response)

    st.success("📝 Result saved to history")


def main():
    st.title("🧠 AI Tester")
    st.markdown("**AI Coding Agent Warmup & Evaluation**")

    # Initialize session state
    if 'current_test_prompt' not in st.session_state:
        st.session_state.current_test_prompt = BASE_PROMPT_TEMPLATE.replace("{num_phases}", "7")
    if 'current_eval_criteria' not in st.session_state:
        st.session_state.current_eval_criteria = DEFAULT_EVALUATION_CRITERIA
    if 'test_is_fresh' not in st.session_state:
        st.session_state.test_is_fresh = False  # No fresh test until they generate one

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Initialize persistent settings in session state
        if 'selected_provider' not in st.session_state:
            st.session_state.selected_provider = "Anthropic"  # Default
        if 'selected_model_idx' not in st.session_state:
            st.session_state.selected_model_idx = 0

        # Provider selection for evaluator
        provider = st.selectbox(
            "Evaluator AI Provider",
            options=["Anthropic", "OpenAI", "Google"],
            index=["Anthropic", "OpenAI", "Google"].index(st.session_state.selected_provider),
            help="AI that will grade the responses",
            key="provider_select"
        )
        st.session_state.selected_provider = provider

        model_options = MODELS.get(provider, {})
        model_keys = list(model_options.keys())
        model_display = st.selectbox(
            "Evaluator Model",
            options=model_keys,
            index=min(st.session_state.selected_model_idx, len(model_keys)-1),
            key="model_select"
        )
        st.session_state.selected_model_idx = model_keys.index(model_display) if model_display in model_keys else 0
        model = model_options.get(model_display, "")

        # API Key - check env vars first
        env_key_map = {"OpenAI": "OPENAI_API_KEY", "Anthropic": "ANTHROPIC_API_KEY", "Google": "GOOGLE_API_KEY"}
        env_var_name = env_key_map.get(provider, "")
        env_api_key = os.environ.get(env_var_name, "")

        if env_api_key:
            # API key found in environment
            st.success(f"✅ {provider} API Key configured")
            api_key = env_api_key
        else:
            # No env var, ask for manual input
            api_key = st.text_input(
                f"{provider} API Key",
                type="password",
                help=f"Set {env_var_name} in Railway env vars to auto-fill"
            )
            if not api_key:
                st.warning(f"⚠️ Set {env_var_name} in Railway")

        st.markdown("---")

        # LLM being tested
        st.subheader("🤖 LLM Under Test")
        llm_tested = st.selectbox(
            "Which LLM are you testing?",
            options=LLMS_UNDER_TEST
        )
        if llm_tested == "Other (specify)":
            llm_tested = st.text_input("Enter LLM name")

        st.markdown("---")
        st.markdown("### Result Guide")
        for key, info in RESULT_TYPES.items():
            st.markdown(f"{info['icon']} **{key.replace('_', ' ')}**: {info['description']}")

    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Create Test", "📊 Evaluate", "📁 Templates", "📜 History"])

    # TAB 1: Create Test
    with tab1:
        st.header("Create or Customize Test")

        st.info("💡 **Quick Start:** Just go to the **Evaluate** tab and click **Generate Fresh Test**. Each click creates a new random test!")

        st.markdown("---")

        # Main action - Generate new test
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("🎲 Generate Random Test")
            st.markdown("Creates a new test with random questions (different fake tech, different contradictions, different code challenges)")
        with col2:
            if st.button("🎲 Regenerate Test", type="primary", use_container_width=True):
                new_prompt, new_criteria, variants = generate_randomized_test()
                st.session_state.current_test_prompt = new_prompt
                st.session_state.current_eval_criteria = new_criteria
                st.session_state.test_variants = variants
                st.session_state.generated_test = new_prompt
                st.session_state.test_is_fresh = True  # Mark as fresh/unused
                st.rerun()

        # Show current test info
        if 'test_variants' in st.session_state:
            v = st.session_state.test_variants
            st.success(f"🎯 **Current Test:** Fake tech = `{v.get('fake_tech', 'N/A')}` | Contradiction = `{v.get('contradiction', 'N/A')[:40]}...` | Function = `{v.get('function', 'N/A')}`")

        # COPY BUTTON - Glows green if fresh, orange if already copied (but still works)
        st.markdown("")
        if 'test_variants' in st.session_state:
            test_to_copy = st.session_state.get('generated_test', st.session_state.current_test_prompt)
            already_copied = not st.session_state.test_is_fresh
            copy_html = copy_button_with_js(test_to_copy, "📋 COPY TEST TO CLIPBOARD", "create_tab", already_copied)
            st.components.v1.html(copy_html, height=70)
            if already_copied:
                st.caption("🔄 Want a new test? Click **Regenerate Test** above")
        else:
            st.info("👆 Click **Regenerate Test** to create a fresh test")

        st.markdown("---")

        # Optional: Project-specific testing
        with st.expander("➕ Add Project-Specific Questions (Optional)"):
            project_desc = st.text_area(
                "What are you about to build?",
                height=100,
                placeholder="Describe the project... (optional - adds an extra phase to the test)",
                help="This adds an 8th phase asking about your specific project"
            )
            include_project_phase = st.checkbox(
                "Include project-specific phase",
                value=bool(project_desc),
            )

        # Advanced: Edit test directly (collapsed by default)
        with st.expander("🔧 Advanced: Edit Test Directly"):
            edited_prompt = st.text_area(
                "Test Prompt",
                value=st.session_state.current_test_prompt,
                height=300,
            )
            st.session_state.current_test_prompt = edited_prompt

            st.markdown("##### Answer Key (Evaluation Criteria)")
            edited_criteria = st.text_area(
                "How to grade responses",
                value=st.session_state.current_eval_criteria,
                height=200,
            )
            st.session_state.current_eval_criteria = edited_criteria

        # Templates section (collapsed)
        with st.expander("📁 Templates"):
            col1, col2 = st.columns(2)
            with col1:
                templates = load_templates()
                if templates:
                    template_choice = st.selectbox(
                        "Load template",
                        options=["-- Select --"] + list(templates.keys())
                    )
                    if template_choice != "-- Select --" and st.button("📂 Load"):
                        template = templates[template_choice]
                        st.session_state.current_test_prompt = template.get("prompt", BASE_PROMPT_TEMPLATE)
                        st.session_state.current_eval_criteria = template.get("criteria", DEFAULT_EVALUATION_CRITERIA)
                        st.rerun()
                else:
                    st.info("No templates saved yet")
            with col2:
                if st.button("🔄 Reset to Default"):
                    st.session_state.current_test_prompt = BASE_PROMPT_TEMPLATE.replace("{num_phases}", "7")
                    st.session_state.current_eval_criteria = DEFAULT_EVALUATION_CRITERIA
                    if 'test_variants' in st.session_state:
                        del st.session_state.test_variants
                    st.rerun()

        # Show current test prompt
        st.markdown("---")
        st.subheader("📋 Current Test (Copy This)")

        final_prompt = generate_test_prompt(
            st.session_state.current_test_prompt,
            project_desc if include_project_phase else None,
            include_project_phase
        )

        st.code(final_prompt, language="markdown")
        st.info("👆 Copy the test above and paste it to any LLM you want to evaluate, or go to **Evaluate** tab for the full workflow")

    # TAB 2: Evaluate
    with tab2:
        st.header("Evaluate Agent Response")

        # Quick test generation right in the Evaluate tab
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### Step 1: Get a Fresh Test")
            st.markdown("Click to generate a new random test (different questions each time)")

        with col2:
            if st.button("🎲 Generate Fresh Test", type="primary", use_container_width=True):
                new_prompt, new_criteria, variants = generate_randomized_test()
                st.session_state.current_test_prompt = new_prompt
                st.session_state.current_eval_criteria = new_criteria
                st.session_state.test_variants = variants
                st.session_state.generated_test = new_prompt
                st.session_state.test_is_fresh = True  # Mark as fresh
                st.session_state.show_test_to_copy = False  # Reset copy view
                st.rerun()

        # Show current test info
        if 'test_variants' in st.session_state:
            v = st.session_state.test_variants
            st.success(f"🎯 Current test: Fake tech = **{v.get('fake_tech', 'N/A')}** | Function = **{v.get('function', 'N/A')}**")

        # COPY BUTTON - Glows green if fresh, orange if already copied (but still works)
        test_to_use = st.session_state.get('generated_test', st.session_state.current_test_prompt)

        if 'test_variants' in st.session_state:
            already_copied = not st.session_state.test_is_fresh
            copy_html = copy_button_with_js(test_to_use, "📋 COPY TEST TO CLIPBOARD", "eval_tab", already_copied)
            st.components.v1.html(copy_html, height=70)
            if already_copied:
                st.caption("🔄 Want a new test? Click **Generate Fresh Test** above")
        else:
            st.info("👆 Click **Generate Fresh Test** to create a test")

        st.markdown("---")
        st.markdown("### Step 2: Paste the LLM's Response")
        response = st.text_area(
            "Agent's complete response",
            height=400,
            placeholder="Paste the agent's response to all phases here..."
        )

        uploaded_file = st.file_uploader("Or upload a text file", type=["txt", "md"])
        if uploaded_file:
            response = uploaded_file.read().decode("utf-8")
            st.text_area("Loaded response:", value=response[:500] + "...", height=100, disabled=True)

        st.markdown("---")
        st.markdown("### Step 3: Evaluate")

        if st.button("🔍 Evaluate Response", type="primary", disabled=not response or not api_key, use_container_width=True):
            if not api_key:
                st.error("Please enter your API key in the sidebar")
            elif not response:
                st.error("Please paste the agent's response")
            elif not llm_tested:
                st.error("Please select which LLM you're testing in the sidebar")
            else:
                with st.spinner(f"Evaluating with {model_display}..."):
                    try:
                        if provider == "OpenAI":
                            results = evaluate_with_openai(api_key, model, test_to_use, response, st.session_state.current_eval_criteria)
                        elif provider == "Anthropic":
                            results = evaluate_with_anthropic(api_key, model, test_to_use, response, st.session_state.current_eval_criteria)
                        else:
                            results = evaluate_with_gemini(api_key, model, test_to_use, response, st.session_state.current_eval_criteria)

                        display_results(results, llm_tested, test_to_use, response)

                    except json.JSONDecodeError as e:
                        st.error(f"Failed to parse evaluation: {e}")
                    except Exception as e:
                        st.error(f"Evaluation failed: {e}")

        if not api_key:
            st.warning("⚠️ Enter your API key in the sidebar to enable evaluation")

    # TAB 3: Templates
    with tab3:
        st.header("Manage Templates")

        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("💾 Save Current as Template")

            template_name = st.text_input("Template Name", placeholder="e.g., React Dashboard Test")
            template_desc = st.text_area(
                "Description",
                placeholder="What kind of project is this template for?",
                height=100
            )
            template_category = st.selectbox(
                "Category",
                options=["General", "Web Frontend", "Backend API", "Full Stack", "Data/ML", "DevOps", "Mobile", "Other"]
            )

            if st.button("💾 Save Template", disabled=not template_name):
                save_template(
                    template_name,
                    st.session_state.current_test_prompt,
                    st.session_state.current_eval_criteria,
                    template_desc,
                    template_category
                )
                st.success(f"Saved template: {template_name}")
                st.rerun()

        with col2:
            st.subheader("📁 Existing Templates")

            templates = load_templates()
            if templates:
                for name, data in templates.items():
                    with st.expander(f"📄 {name}"):
                        st.markdown(f"**Category:** {data.get('category', 'General')}")
                        st.markdown(f"**Description:** {data.get('description', 'No description')}")
                        st.markdown(f"**Created:** {data.get('created', 'Unknown')[:10]}")

                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("📂 Load", key=f"load_{name}"):
                                st.session_state.current_test_prompt = data.get("prompt", BASE_PROMPT_TEMPLATE)
                                st.session_state.current_eval_criteria = data.get("criteria", DEFAULT_EVALUATION_CRITERIA)
                                st.success(f"Loaded: {name}")
                                st.rerun()
                        with col_b:
                            if st.button("🗑️ Delete", key=f"del_{name}"):
                                delete_template(name)
                                st.success(f"Deleted: {name}")
                                st.rerun()
            else:
                st.info("No templates saved yet. Create one from the 'Create Test' tab!")

    # TAB 4: History
    with tab4:
        st.header("Test History")

        history = load_history()

        if history:
            # Summary stats
            col1, col2, col3, col4 = st.columns(4)

            total = len(history)
            go_count = sum(1 for h in history if h.get('result') in ['GO', 'GO_WITH_CHECKS'])
            fail_count = sum(1 for h in history if h.get('result') in ['SKIP', 'CRITICAL_FAIL'])

            with col1:
                st.metric("Total Tests", total)
            with col2:
                st.metric("Passed", go_count)
            with col3:
                st.metric("Failed", fail_count)
            with col4:
                pass_rate = (go_count / total * 100) if total > 0 else 0
                st.metric("Pass Rate", f"{pass_rate:.0f}%")

            st.markdown("---")

            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                filter_llm = st.selectbox("Filter by LLM", options=["All"] + list(set(h.get('llm_tested', '') for h in history)))
            with col2:
                filter_result = st.selectbox("Filter by Result", options=["All"] + list(RESULT_TYPES.keys()))

            # Display history
            for entry in history:
                if filter_llm != "All" and entry.get('llm_tested') != filter_llm:
                    continue
                if filter_result != "All" and entry.get('result') != filter_result:
                    continue

                result = entry.get('result', 'SKIP')
                result_info = RESULT_TYPES.get(result, RESULT_TYPES['SKIP'])

                with st.expander(
                    f"{result_info['icon']} {entry.get('llm_tested', 'Unknown')} - {result.replace('_', ' ')} - {entry.get('timestamp', '')[:10]}"
                ):
                    st.markdown(f"**Score:** {entry.get('score', 'N/A')} points")
                    st.markdown(f"**Template:** {entry.get('template', 'Default')}")
                    st.markdown(f"**Summary:** {entry.get('summary', 'No summary')}")

                    if entry.get('phases'):
                        st.markdown("**Phase Results:**")
                        for phase in entry['phases']:
                            status = phase.get('status', '?')
                            icon = {"PASS": "✅", "CONCERN": "⚠️", "FAIL": "❌"}.get(status, "?")
                            st.markdown(f"- {icon} Phase {phase.get('phase', '?')}: {phase.get('name', '?')} - {status}")

            st.markdown("---")
            if st.button("🗑️ Clear History"):
                clear_history()
                st.success("History cleared")
                st.rerun()
        else:
            st.info("No test history yet. Run some evaluations!")


if __name__ == "__main__":
    main()
