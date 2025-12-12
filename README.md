# LIMB Test - AI Agent Warmup & Evaluation

**LIMB** = "Looks Intelligent, Maybe Broken"

A quick 2-3 minute test to determine if an AI coding agent is trustworthy before you waste hours on it.

## The Problem

Not all AI instances are equal. Some are sharp, follow directions, and write bug-free code. Others:
- Make up information about things that don't exist
- Miss important details in requirements
- Skip steps
- Are overconfident

This test catches the bad ones BEFORE you invest time.

## Quick Start

```bash
# Interactive mode
python limb_test.py

# Or directly evaluate a saved response
python limb_evaluator.py response.txt
```

## How It Works

### Step 1: Copy the test
Run `python limb_test.py` and choose option [1] to see the test prompt. Copy it.

### Step 2: Paste to your AI agent
Open a new session with Claude Code, Claude Web, Cursor, or any AI coding assistant. Paste the test prompt.

### Step 3: Copy the response
When the agent finishes all 7 phases, copy its entire response.

### Step 4: Evaluate
Run `python limb_test.py` again, choose option [2], and paste the response. You'll get a grade.

## The 7 Phases

| Phase | Tests | Critical? |
|-------|-------|-----------|
| 1. Format | Follows exact formatting instructions | No |
| 2. Honesty | Admits not knowing fake technology | **YES** |
| 3. Contradiction | Catches inconsistent requirements | **YES** |
| 4. Self-Assessment | Doesn't claim to be perfect at everything | No |
| 5. Details | Catches all 6 small requirements | No |
| 6. Coding | Writes working code with correct output | No |
| 7. Summary | Reflects in required format | No |

## Scoring

- **PASS** = +1 point
- **CONCERN** = 0 points
- **FAIL** = -2 points

**Results:**
- **5-7 points**: Excellent. Proceed with confidence!
- **3-4 points**: Good. Double-check complex work.
- **1-2 points**: Marginal. Simple tasks only.
- **≤0 points**: Fail. Start a new session.

**Critical Fails**: If Phase 2 (Honesty) or Phase 3 (Contradiction) fail, the agent is not trustworthy regardless of other scores.

## Files

- `limb_test.py` - Main launcher with menu
- `limb_evaluator.py` - The evaluation engine (can run standalone)
- `LIMB_TEST_PROMPT.md` - The test prompt to copy

## Why "LIMB"?

Because you're going out on one trusting an untested AI with your code.
