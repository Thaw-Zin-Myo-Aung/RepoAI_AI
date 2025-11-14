# Conversational Intent Detection in Orchestrator

## Overview

The RepoAI orchestrator now includes **conversational intent detection** to handle greetings, questions, and general chat **before** starting the refactoring pipeline. This creates a more natural user experience, especially for first-time users.

## How It Works

### Pre-Flight Check

Before running the full refactoring pipeline, the orchestrator performs a **pre-flight check** using `_check_conversational_intent()`:

```python
# In orchestrator.run()
conversational_response = await self._check_conversational_intent(user_prompt)
if conversational_response:
    # This is a greeting/question, not a refactoring request
    self._send_progress(conversational_response)
    self.state.status = PipelineStatus.COMPLETED
    self.state.stage = PipelineStage.COMPLETE
    return self.state

# Otherwise, proceed with pipeline...
```

### Detection Strategy

The system uses a **hybrid approach** combining heuristics and LLM classification:

#### 1. **Fast Heuristic Matching** (No LLM Call)

Detects common patterns instantly:

**Greetings:**
- `"hi"`, `"hello"`, `"hey"`, `"good morning"`, etc.
- Returns friendly introduction to RepoAI

**Capability Questions:**
- `"what can you do"`, `"help"`, `"how does this work"`, etc.
- Returns detailed capabilities list

**Thanks/Goodbye:**
- `"thanks"`, `"thank you"`, `"bye"`, `"goodbye"`
- Returns friendly acknowledgment

#### 2. **LLM Classification** (Fallback for Ambiguous Cases)

For inputs that don't match heuristics:
- Uses `run_raw_async()` with ORCHESTRATOR role
- Temperature: **0.1** (very deterministic)
- Prompt asks for simple classification: `"CONVERSATIONAL"` or `"REFACTORING"`
- Only 10 tokens needed for response

```python
prompt = """Analyze this user input and determine if it's a conversational message 
(greeting, question about capabilities, small talk) or a code refactoring request.

**User Input:** "{user_prompt}"

Respond with ONLY ONE WORD: either "CONVERSATIONAL" or "REFACTORING"."""
```

## Supported Conversational Inputs

### 1. **Greetings**

**Inputs:**
- `"hello"`
- `"hi"`
- `"hey"`
- `"good morning"`
- `"Hi there!"`

**Response:**
```
👋 Hello! I'm **RepoAI**, your intelligent code refactoring assistant.

I can help you:
- 🔨 Refactor and modernize your codebase
- ✨ Add new features to your application
- 🐛 Fix bugs and improve code quality
- 📦 Migrate to new frameworks or libraries

Just describe what you'd like me to do with your code, and I'll create a plan, 
make the changes, validate them, and prepare everything for a pull request!

**Example requests:**
- "Add JWT authentication to the user service"
- "Refactor the payment module to use async/await"
- "Migrate from JUnit 4 to JUnit 5"
```

### 2. **Capability Questions**

**Inputs:**
- `"what can you do"`
- `"help"`
- `"how does this work"`
- `"what is repoai"`
- `"what are you"`
- `"who are you"`

**Response:**
```
🤖 I'm **RepoAI**, an AI-powered code refactoring assistant!

**What I can do:**

1. **Analyze** your refactoring request using natural language
2. **Plan** a detailed strategy for the changes
3. **Generate** the necessary code modifications
4. **Validate** changes by compiling and running tests
5. **Create** comprehensive PR descriptions
6. **Push** changes to GitHub when you're ready

**I work with:**
- Java (Spring Boot, Maven, Gradle)
- Python (FastAPI, Django, Flask)
- JavaScript/TypeScript (Node.js, React)

**Example:** Tell me "Add caching to the database queries" and I'll handle the rest!
```

### 3. **Thanks/Goodbye**

**Inputs:**
- `"thanks"`
- `"thank you"`
- `"bye"`
- `"goodbye"`

**Response:**
```
👍 You're welcome! Feel free to ask me to refactor your code anytime.

Happy coding! 🚀
```

### 4. **LLM-Detected Conversational**

For ambiguous inputs classified by LLM:

**Response:**
```
👋 Hi there! I'm RepoAI, your code refactoring assistant.

I specialize in making intelligent code changes to your repository. 
Just describe what you'd like me to refactor or improve, and I'll handle the rest!

**Try asking me to:**
- Add new features to your code
- Refactor existing modules
- Migrate to new frameworks
- Improve code quality

What would you like me to help you with?
```

## What Gets Classified as Refactoring

**These inputs will NOT be detected as conversational:**

- `"Add JWT authentication"` ✅ Refactoring request
- `"Refactor the database layer"` ✅ Refactoring request
- `"Migrate to Python 3.12"` ✅ Refactoring request
- `"Fix the memory leak in cache"` ✅ Refactoring request
- `"Improve performance"` ✅ Refactoring request
- `"Update dependencies"` ✅ Refactoring request

The system errs on the side of **treating ambiguous inputs as refactoring requests** to avoid blocking valid work.

## API Behavior

### Request

```bash
POST /api/v1/refactor
{
  "user_id": "developer_001",
  "user_prompt": "hello",
  "github_credentials": {...},
  "mode": "interactive-detailed"
}
```

### Response Flow

1. **Session created** immediately with session_id
2. **Progress queue** receives conversational response:
   ```json
   {
     "event_type": "progress",
     "message": "👋 Hello! I'm **RepoAI**..."
   }
   ```
3. **State completes** without running any agents:
   ```json
   {
     "session_id": "session_20251113_143022",
     "status": "completed",
     "stage": "complete",
     "job_spec": null,
     "plan": null,
     "code_changes": null
   }
   ```

### SSE Stream

```
data: {"event_type": "progress", "message": "👋 Hello! I'm **RepoAI**..."}

data: {"event_type": "complete", "message": "Conversation completed"}
```

## Implementation Details

### Method Signature

```python
async def _check_conversational_intent(self, user_prompt: str) -> str | None:
    """
    Check if user prompt is conversational rather than a refactoring request.

    Returns:
        Response message if conversational, None if it's a refactoring request
    """
```

### Performance

- **Heuristic matches:** ~0.1ms (instant)
- **LLM classification:** ~200-500ms (only for ambiguous cases)
- **Most greetings:** Handled without LLM call

### Error Handling

If LLM fails during classification:

```python
except Exception as e:
    logger.warning(f"Failed to check conversational intent: {e}")
    # Assume it's a refactoring request (safe default)
    return None
```

This ensures the system **never blocks valid refactoring requests** due to classification errors.

## Benefits

### For Users
- ✅ **Natural onboarding** - New users can start with "hello"
- ✅ **Self-discovery** - Users can ask "what can you do?"
- ✅ **Friendly interaction** - More human-like conversation
- ✅ **No confusion** - Clear guidance on how to use RepoAI

### For Developers
- ✅ **Better UX** - Reduces confusion about capabilities
- ✅ **Fast** - Heuristics avoid unnecessary LLM calls
- ✅ **Safe** - Defaults to refactoring on uncertainty
- ✅ **Extensible** - Easy to add more conversational patterns

## Future Enhancements

### 1. **Context-Aware Responses**

Track conversation history to provide personalized responses:

```
User: "hello"
RepoAI: "👋 Welcome back! Ready to continue where we left off?"
```

### 2. **Multi-Turn Clarification**

Handle follow-up questions before starting refactoring:

```
User: "I want to add authentication"
RepoAI: "Great! What type of authentication? JWT, OAuth, or session-based?"
User: "JWT"
RepoAI: "Perfect! Starting refactoring for JWT authentication..."
```

### 3. **Capability Demonstrations**

Show examples based on detected project type:

```
User: "what can you do"
RepoAI: "I detected you're using Spring Boot! Here are some things I can do for your project:
- Add JWT authentication with Spring Security
- Migrate to Spring Boot 3
- Add Redis caching
..."
```

### 4. **Sentiment Analysis**

Detect frustrated users and offer help:

```
User: "this isn't working"
RepoAI: "I'm sorry you're having trouble! Can you tell me more about what's not working? I'm here to help!"
```

## Testing

### Manual Testing

```bash
# Test greeting
curl -X POST http://localhost:8000/api/v1/refactor \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "user_prompt": "hello",
    "mode": "interactive-detailed"
  }'

# Test capability question
curl -X POST http://localhost:8000/api/v1/refactor \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "user_prompt": "what can you do?",
    "mode": "interactive-detailed"
  }'

# Test refactoring (should NOT be conversational)
curl -X POST http://localhost:8000/api/v1/refactor \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test",
    "user_prompt": "Add JWT authentication",
    "mode": "interactive-detailed"
  }'
```

### Expected Behavior

✅ **Greeting** → Conversational response, no pipeline execution
✅ **Capability question** → Detailed capabilities, no pipeline execution  
✅ **Refactoring request** → Full pipeline execution with all stages

## Demo Script (Nov 17)

Showcase the conversational capability:

### Demo Flow

1. **First interaction - Greeting:**
   ```
   User: "hi"
   RepoAI: "👋 Hello! I'm RepoAI, your intelligent code refactoring assistant..."
   ```

2. **User asks about capabilities:**
   ```
   User: "what can you do?"
   RepoAI: "🤖 I'm RepoAI, an AI-powered code refactoring assistant!
   I can analyze, plan, generate, validate, create PRs, and push changes..."
   ```

3. **User makes refactoring request:**
   ```
   User: "Add JWT authentication to the user service"
   RepoAI: "🚀 Starting pipeline: Add JWT authentication...
   📥 Stage 1: Analyzing refactoring request..."
   [Full pipeline executes]
   ```

This demonstrates that RepoAI is **smart enough to know when to chat vs when to work!** 🎯

## Conclusion

The conversational intent detection feature makes RepoAI more **approachable and user-friendly**, especially for first-time users. It provides a natural onboarding experience while maintaining the robust refactoring pipeline for actual work requests.

The hybrid heuristic + LLM approach ensures:
- ⚡ **Fast response** for common cases
- 🎯 **Accurate classification** for ambiguous cases
- 🛡️ **Safe defaults** that never block valid refactoring requests

Perfect for the **Nov 17 demo** to show the AI's intelligence in understanding context! 🚀
