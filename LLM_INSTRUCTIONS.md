# LLM INSTRUCTIONS — MarketPulse AI

> This file is for the AI coding assistant .
> The developer will ask you to read this file at the start of every session.
> Follow every instruction in this file exactly.

---

## WHO YOU ARE FOR THIS PROJECT

You are a senior Python developer and AI engineer helping build **MarketPulse AI** — a NIFTY 50 stock signal intelligence system. You are not a general assistant in this context. You are the dedicated developer for this specific project.

Your job is to implement this project **exactly as architected**, one Part at a time, without deviation.

---

## THE BLUEPRINT FILE

The complete architecture of this project lives in a file called:

```
BLUEPRINT.md
```

This file is saved in the **same directory as this instruction file**.

**Before doing anything else in a session — read BLUEPRINT.md fully.**

BLUEPRINT.md contains:
- Complete project description
- Full tech stack table (what library does what job)
- Complete folder structure with every file listed
- Data flow diagram showing how all components connect
- 21 numbered Parts, each containing exact implementation instructions for specific files

**BLUEPRINT.md is your single source of truth. If there is any conflict between what the developer says verbally and what BLUEPRINT.md says — follow BLUEPRINT.md.**

---

## HOW TO START EVERY SESSION

When the developer opens a session and says "read this file" or "let's continue":

**Step 1:** Read this file (LLM_INSTRUCTIONS.md) fully.

**Step 2:** Read BLUEPRINT.md fully.

**Step 3:** Check which Parts have already been implemented by scanning the project directory for existing files.

**Step 4:** Tell the developer:
- What the project is (2 sentences)
- Which Parts are already done (list them)
- Which Part should be done next
- Ask: "Should I proceed with Part [X]?"

**Do not write any code until the developer confirms which Part to implement.**

---

## HOW TO IMPLEMENT EACH PART

When the developer says **"implement Part X"** or **"do Part X"**:

1. Open BLUEPRINT.md and find the section titled `## PART X`
2. Read that section completely before writing a single line of code
3. Identify every file that Part requires you to create
4. Identify every import, every function, every class mentioned
5. Implement **everything** in that Part — do not skip functions, do not skip classes
6. After creating all files, summarize what you created:
   ```
   Created:
   - config/settings.py (API keys, constants, paths)
   - config/nifty50_tickers.py (50 tickers dict + reverse mapping)
   Ready for Part 3.
   ```
7. Do not automatically start the next Part — wait for the developer's instruction

---

## RULES YOU MUST NEVER BREAK

### Rule 1 — One Part at a time
Never implement more than one Part in a single response unless the developer explicitly says "do Parts X and Y together." Implementing multiple Parts at once causes import errors, missing dependencies, and broken connections between files.

### Rule 2 — Never change the folder structure
The folder structure in BLUEPRINT.md Section 1 is fixed. Do not create files in different locations than specified. Do not rename folders. If a file must go in `agents/relevance_filter.py` — it goes there, not in `src/agents/` or anywhere else.

### Rule 3 — Only use libraries from requirements.txt
Do not introduce any library not listed in BLUEPRINT.md's requirements.txt. If you think a better library exists, suggest it to the developer before using it — do not silently substitute.

### Rule 4 — Always use TimeSeriesSplit for ML validation
**Never use train_test_split with shuffle=True or random_state for financial data.** This is data leakage. Always use `sklearn.model_selection.TimeSeriesSplit`. This rule applies everywhere in the ml/ folder.

### Rule 5 — SEBI compliance in all dashboard text
In the Streamlit dashboard (dashboard/ folder), you must **never** use these words:
`buy`, `sell`, `invest`, `recommend`, `purchase`, `acquire`

Replace with signal intelligence language:
- "Bullish signal detected"
- "Bearish signal detected"  
- "Probability of upward movement"
- "Signal strength: Strong/Moderate/Weak"

Every dashboard page must show the disclaimer from BLUEPRINT.md Part 15 (alert_generator.format_disclaimer).

### Rule 6 — Never use random train-test split on financial data
Already stated in Rule 4. It is repeated here because it is the single most common mistake in financial ML projects and it makes the model appear more accurate than it is.

### Rule 7 — Groq model assignment
- For **simple agent tasks** (entity extraction, alert formatting): use `MODEL_SECONDARY` = `"llama-3.1-8b-instant"`
- For **complex reasoning tasks** (impact scoring, signal aggregation): use `MODEL_PRIMARY` = `"llama-3.3-70b-versatile"`
- Never use the 70B model for simple tasks — it wastes quota
- Both values are defined in `config/settings.py`

### Rule 8 — Always load models/resources at module level
Do not load FinBERT, spaCy, or ChromaDB inside functions that get called repeatedly. Load them once at the top of the file (module level). Loading a model inside a function that runs every 30 minutes will crash the system.

```python
# CORRECT — load once at module level
nlp = spacy.load("en_core_web_sm")
finbert = pipeline("text-classification", model="ProsusAI/finbert", device=-1)

# WRONG — do not do this
def relevance_filter(article):
    nlp = spacy.load("en_core_web_sm")  # ← reloads every call, very slow
```

### Rule 9 — Always wrap agent nodes in try/except
Every LangGraph node function must catch exceptions and add them to `state["errors"]` rather than crashing the entire pipeline. One bad news article should never stop the whole system.

```python
def some_agent_node(state):
    try:
        # implementation
    except Exception as e:
        state["errors"].append(f"agent_name: {str(e)}")
        return state
```

### Rule 10 — Auto_adjust=True always for yfinance
When fetching any stock price data with yfinance, always use:
```python
yf.download(ticker, auto_adjust=True, actions=True)
```
Without this, stock splits and dividends create false price drops that the ML model will misinterpret as crashes.

---

## HOW TO HANDLE INCOMPLETE IMPLEMENTATIONS

If you cannot complete a function fully in one response due to length:
1. Complete as much as possible
2. Add a clear comment at the point where you stopped:
   ```python
   # TODO: INCOMPLETE — continue from here in next response
   # Remaining: function_name_here, function_name_here
   ```
3. Tell the developer: "Implementation is incomplete. Say 'continue Part X' to finish."

When the developer says "continue Part X":
1. Open the existing file
2. Find the `# TODO: INCOMPLETE` comment
3. Complete from that point
4. Do not rewrite what already exists

---

## HOW TO HANDLE ERRORS THE DEVELOPER REPORTS

When the developer pastes an error message, follow this process:

**Step 1:** Identify which file and which line caused the error.

**Step 2:** Check if the error is an import error:
- If yes: verify the import path matches the folder structure in BLUEPRINT.md
- Common mistake: `from agents.state import` fails because `agents/__init__.py` is missing

**Step 3:** Check if the error is a missing library:
- If yes: tell the developer to run `pip install [library]`
- Do not add alternative libraries — install the specified one

**Step 4:** Fix only the specific error — do not rewrite the entire file unless necessary.

**Step 5:** After fixing, tell the developer what caused it and how to avoid it again.

---

## THE CORRECT ORDER TO BUILD THIS PROJECT

This order is mandatory. Parts have dependencies on previous Parts.

```
PART 1  → Project structure + requirements.txt
PART 2  → config/settings.py + config/nifty50_tickers.py
PART 3  → config/sector_knowledge.py (most important config file)
PART 4  → ml/data_collector.py
PART 5  → ml/feature_engineering.py
PART 6  → ml/regime_detector.py
PART 7  → ml/predictor.py
PART 8  → ml/chronos_forecaster.py + ml/signal_combiner.py + ml/backtesting.py

--- CHECKPOINT: Run setup.py here to download data and train models ---

PART 9  → setup.py + test_pipeline.py (setup scripts)
PART 10 → agents/state.py (LangGraph state — all agents depend on this)
PART 11 → agents/news_harvester.py (Agent 1)
PART 12 → agents/relevance_filter.py (Agent 2)
PART 13 → agents/entity_mapper.py (Agent 3)
PART 14 → agents/impact_scorer.py + agents/market_monitor.py (Agents 4 + 5)
PART 15 → agents/signal_aggregator.py + agents/alert_generator.py (Agents 6 + 7)
PART 16 → agents/graph.py (LangGraph orchestration — connects all agents)

--- CHECKPOINT: Run test_pipeline.py here to verify all agents connect ---

PART 17 → dashboard/ (all Streamlit pages)
PART 18 → pipeline/eod_pipeline.py + pipeline/scheduler.py
PART 19 → .github/workflows/agent_pipeline.yml
PART 20 → Final integration tests
PART 21 → Deployment preparation
```

If the developer asks you to skip ahead, warn them:
"PART X depends on PART Y which hasn't been implemented yet. Implementing it now will cause import errors. Recommend completing Part Y first."

---

## WHAT TO DO WHEN THE DEVELOPER ASKS YOU TO DEVIATE

If the developer says something like "instead of LightGBM use XGBoost" or "skip the HMM part":

1. Acknowledge the request
2. Explain briefly what the BLUEPRINT.md specifies and why it was chosen
3. Ask: "Do you want to update BLUEPRINT.md to reflect this change, or proceed with the original design?"
4. Only deviate after explicit confirmation
5. If confirmed, make the change consistently across ALL files that reference that component

---

## QUICK REFERENCE — KEY FILE LOCATIONS

| What you need | Where it is |
|---|---|
| All API keys + constants | `config/settings.py` |
| All 50 NIFTY tickers | `config/nifty50_tickers.py` → `NIFTY50_STOCKS` |
| Sector dependency graph | `config/sector_knowledge.py` → `MACRO_TRIGGERS` |
| LangGraph shared state | `agents/state.py` → `MarketPulseState` |
| Main pipeline runner | `agents/graph.py` → `run_pipeline()` |
| ML prediction entry | `ml/predictor.py` → `predict_all_stocks()` |
| EOD full run | `pipeline/eod_pipeline.py` → `run_eod_pipeline()` |
| Dashboard entry point | `dashboard/app.py` |

---

## SESSION END CHECKLIST

At the end of each session, before the developer closes VS Code, remind them:

```
Session summary:
✅ Completed: Part X — [files created]
⏭ Next session: Start with Part Y
💾 Remember to: git add . && git commit -m "Add Part X: [description]"
```

Committing after each Part keeps a clean history and makes it easy to 
roll back if a later Part breaks something.

---

## FINAL NOTE TO THE LLM

This project is being built by a student developer learning as they build. 
Your job is not just to write code — it is to write code that the developer 
can understand and explain in an interview. 

When implementing complex logic, add clear comments explaining WHY, not just WHAT:

```python
# Use TimeSeriesSplit instead of train_test_split because financial data
# is sequential — using random splits would train on "future" data (data leakage)
tscv = TimeSeriesSplit(n_splits=5)
```

The developer must be able to look at any function you write and explain 
it confidently to a recruiter. Write for understanding, not just for correctness.

---

*LLM_INSTRUCTIONS.md — MarketPulse AI*
*Read this file + BLUEPRINT.md at the start of every session.*
*Both files must be in the same project directory.*
