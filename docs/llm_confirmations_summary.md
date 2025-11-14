# LLM-Powered Natural Language Confirmations ✅

## Overview

Enhanced the orchestrator confirmation system to support **both structured and natural language inputs**, using LLM to intelligently interpret user intent.

## The Problem You Identified

You correctly pointed out that in Phase 1, we designed `_interpret_user_intent()` to use LLM for understanding natural language, but in Phase 2, I implemented only hard-coded structured actions like `{"action": "approve"}`.

## The Solution

Implemented a **hybrid approach** that supports:

### 1. Structured Format (Programmatic API)
```json
{"action": "approve"}
{"action": "modify", "modifications": "Add logging to all methods"}
{"action": "cancel"}
```
**Use case**: Backend programmatic calls, automated systems

### 2. Natural Language Format (Interactive Chat)
```json
{"user_response": "yes, looks great!"}
{"user_response": "yes but please use Redis cache instead of in-memory"}
{"user_response": "no, this is too risky for production"}
```
**Use case**: Interactive chat, human users typing responses

## How It Works

### Plan Confirmation Flow with LLM

1. **User submits natural language**: `{"user_response": "yes but use Redis instead"}`
2. **API endpoint** receives request, validates format
3. **Endpoint** puts `{"user_response": "..."}` in confirmation queue
4. **Orchestrator** detects `user_response` field
5. **Orchestrator** calls `_interpret_user_intent(user_response, plan_summary)`
6. **LLM analyzes** the response in context of the plan
7. **LLM returns** `OrchestratorDecision`:
   - `action`: "approve", "modify", "cancel", or "clarify"
   - `reasoning`: Why it interpreted this way
   - `confidence`: How confident (0.0-1.0)
   - `modifications`: Extracted modification instructions
8. **Orchestrator** acts on LLM decision (continue/modify/cancel)

### Example LLM Interpretation

**User says**: "yes but please use Redis cache instead of in-memory cache"

**LLM interprets**:
```json
{
  "action": "modify",
  "reasoning": "User approves the plan but requests a specific technology change",
  "confidence": 0.95,
  "modifications": "Use Redis cache instead of in-memory cache for the caching layer"
}
```

## Code Changes

### 1. Enhanced `_wait_for_plan_confirmation()` Method

**Before** (Phase 2 initial):
```python
action = confirmation.get("action")
modifications = confirmation.get("modifications")
```

**After** (With LLM support):
```python
# Check if this is a natural language response
if "user_response" in confirmation:
    logger.info("Received natural language response, using LLM to interpret...")
    user_response = str(confirmation["user_response"])
    
    # Use LLM to interpret user intent
    decision = await self._interpret_user_intent(user_response, plan_summary)
    
    # Map LLM decision to action
    action: str = decision.action
    modifications: str | None = decision.modifications
else:
    # Structured format (backward compatible)
    action = confirmation.get("action")
    modifications = confirmation.get("modifications")
```

### 2. Updated `PlanConfirmationRequest` Model

**New fields**:
```python
class PlanConfirmationRequest(BaseModel):
    action: str | None = Field(
        default=None,
        description="Structured action (use this OR user_response)"
    )
    modifications: str | None = Field(default=None)
    user_response: str | None = Field(
        default=None,
        description="Natural language response (use this OR action)"
    )
```

**Validation**: Must provide either `action` OR `user_response`, not both.

### 3. Enhanced API Endpoint

**`POST /refactor/{session_id}/confirm-plan`** now handles:

```python
# Natural language format
if request.user_response:
    await confirmation_queues[session_id].put(
        {"user_response": request.user_response}
    )
else:
    # Structured format
    await confirmation_queues[session_id].put(
        {"action": request.action, "modifications": request.modifications}
    )
```

## Benefits

### 1. **Intelligent Intent Recognition**
- LLM understands: "yes", "yep", "looks good", "approve", "go ahead"
- LLM extracts modifications from: "yes but use Redis"
- LLM detects cancellation: "no", "too risky", "don't proceed"

### 2. **Clarification Requests**
If LLM can't understand, it returns `action="clarify"`:
```python
elif action == "clarify":
    logger.warning("LLM needs clarification from user")
    self._send_progress(
        "⚠️ Could not understand your response. Please clarify...",
        event_type="clarification_needed",
        requires_confirmation=True
    )
    # Wait for clarification
    await self._wait_for_plan_confirmation()
```

### 3. **Backward Compatible**
- Old code using structured format still works
- Can gradually migrate to natural language
- Both formats coexist peacefully

### 4. **Confidence Tracking**
- LLM returns confidence score (0.0-1.0)
- Low confidence triggers warnings
- Could trigger human review if needed

## Example Requests

### Structured Approval
```bash
curl -X POST http://localhost:8000/api/refactor/session_123/confirm-plan \
  -H "Content-Type: application/json" \
  -d '{"action": "approve"}'
```

### Structured Modification
```bash
curl -X POST http://localhost:8000/api/refactor/session_123/confirm-plan \
  -H "Content-Type: application/json" \
  -d '{
    "action": "modify",
    "modifications": "Add comprehensive logging"
  }'
```

### Natural Language Approval
```bash
curl -X POST http://localhost:8000/api/refactor/session_123/confirm-plan \
  -H "Content-Type: application/json" \
  -d '{"user_response": "yes, looks perfect!"}'
```

### Natural Language Modification
```bash
curl -X POST http://localhost:8000/api/refactor/session_123/confirm-plan \
  -H "Content-Type: application/json" \
  -d '{"user_response": "yes but please use Redis cache instead of in-memory cache and add retry logic"}'
```

### Natural Language Cancellation
```bash
curl -X POST http://localhost:8000/api/refactor/session_123/confirm-plan \
  -H "Content-Type: application/json" \
  -d '{"user_response": "no, this seems too risky for production"}'
```

## Testing Results

All tests passing ✅:
- `test_structured_approval()` - Structured format works
- `test_natural_language_approval()` - LLM interprets "yes, looks perfect!"
- `test_natural_language_modification()` - LLM extracts modification intent
- `test_api_model_supports_both_formats()` - Both inputs accepted

## LLM Decision Actions

The LLM can return these actions:

1. **`approve`**: User approves the plan as-is
   - Examples: "yes", "looks good", "perfect", "go ahead"

2. **`modify`**: User wants changes before proceeding
   - Examples: "yes but use Redis", "add more logging", "change timeout to 30s"
   - Extracts modification instructions automatically

3. **`cancel`**: User rejects the plan
   - Examples: "no", "too risky", "don't do this", "abort"

4. **`clarify`**: LLM needs more information
   - Examples: "maybe", "not sure", ambiguous responses
   - Triggers clarification request back to user

## Integration with Existing Code

The `_interpret_user_intent()` method (from Phase 1) uses:
- **Role**: `ModelRole.ORCHESTRATOR`
- **Prompt**: `USER_INTENT_INSTRUCTIONS` (from prompts module)
- **Schema**: `OrchestratorDecision` (structured output)
- **Temperature**: 0.2 (deterministic)
- **Fallback**: Returns "clarify" if LLM fails

## Files Modified

1. **`src/repoai/orchestrator/orchestrator_agent.py`** (~30 lines changed)
   - Enhanced `_wait_for_plan_confirmation()` with LLM path
   - Added type annotations for clarity
   - Added clarification loop

2. **`src/repoai/api/models.py`** (~40 lines changed)
   - Added `user_response` field to `PlanConfirmationRequest`
   - Made `action` optional (either action or user_response required)
   - Updated documentation with examples

3. **`src/repoai/api/routes/refactor.py`** (~20 lines changed)
   - Added validation for mutually exclusive fields
   - Route confirmation based on input format
   - Enhanced logging

4. **`tests/test_llm_confirmations.py`** (new file, 260 lines)
   - Tests for both formats
   - LLM interpretation tests
   - API model validation

## Quality Checks

- ✅ **Ruff**: All linting checks pass
- ✅ **Mypy**: All type checks pass
- ✅ **Tests**: All confirmation tests pass
- ✅ **Integration**: Works with existing Phase 1 code

## Summary

You were absolutely right to point this out! The system now:

1. ✅ **Supports structured API calls**: `{"action": "approve"}`
2. ✅ **Supports natural language**: `{"user_response": "yes but use Redis"}`
3. ✅ **Uses LLM intelligently**: Interprets intent with confidence scoring
4. ✅ **Handles ambiguity**: Asks for clarification when unsure
5. ✅ **Backward compatible**: Existing code continues to work
6. ✅ **Fully tested**: Both paths validated

The orchestrator is now truly intelligent, understanding both programmatic commands and natural human language! 🎉

---

**Status**: LLM-powered confirmations implemented and tested ✅
