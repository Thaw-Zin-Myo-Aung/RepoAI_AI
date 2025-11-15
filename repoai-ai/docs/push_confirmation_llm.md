# Push Confirmation with LLM Support

## Overview

The push confirmation system now supports **natural language interpretation** using an LLM, making it consistent with plan confirmation. Users can respond to push prompts in natural language instead of structured JSON.

## How It Works

### 1. **Natural Language Support**

When the orchestrator asks for push confirmation, users can respond in natural language:

**Examples:**
- ✅ `"yes, push it"`
- ✅ `"looks good, go ahead"`
- ✅ `"yes but use commit message: Fix critical caching bug"`
- ✅ `"push to feature/optimization branch"`
- ✅ `"cancel, I need to review more"`
- ✅ `"no, abort"`

### 2. **LLM Interpretation Flow**

```
User Response → _interpret_push_intent() → LLM Analysis → OrchestratorDecision
                                                              ↓
                                                     action: approve/cancel/clarify
                                                     modifications: commit message/branch
                                                     confidence: 0.0-1.0
```

### 3. **Supported Actions**

| Action | Description | Examples |
|--------|-------------|----------|
| `approve` | Push changes to GitHub | "yes", "looks good", "push it", "go ahead" |
| `cancel` | Cancel the push | "no", "cancel", "don't push", "abort" |
| `clarify` | Need more information | unclear responses, low confidence |

## API Request Formats

### Natural Language Format (Recommended)

```json
{
  "user_response": "yes, push with commit message: Optimize database queries"
}
```

### Structured Format (Backward Compatible)

```json
{
  "action": "approve",
  "branch_name_override": "feature/optimization",
  "commit_message_override": "Optimize database queries"
}
```

## Commit Message Modification

### Direct Override

When the user provides a custom commit message:

```json
{
  "user_response": "yes but use commit message: Fix memory leak in cache"
}
```

The orchestrator will:
1. **Extract** the commit message from LLM's `modifications` field
2. **Parse** using heuristics: `"commit message: <message>"`
3. **Store** in `state.confirmation_data["message_override"]`
4. **Use** the custom message instead of PR description

### PR Narrator Agent Regeneration

When the user asks to **regenerate** the commit message:

```json
{
  "user_response": "yes but regenerate the commit message"
}
```

The orchestrator will:
1. **Detect** keywords: `"regenerate"`, `"rewrite"`, `"improve"`, `"better"`
2. **Call** PR narrator agent with current code changes
3. **Generate** new comprehensive commit message
4. **Update** `state.pr_description` with new description
5. **Use** the newly generated summary as commit message

**Keywords that trigger regeneration:**
- `"regenerate"` → Full PR narrator agent run
- `"rewrite"` → Full PR narrator agent run
- `"improve"` → Full PR narrator agent run
- `"better"` → Full PR narrator agent run

### Example Flow

```
User: "yes but improve the commit message"
       ↓
Orchestrator detects "improve" keyword
       ↓
Calls PR narrator agent:
  - Input: code_changes, validation_result
  - Output: new PR description with title, summary, changes
       ↓
Uses pr_description.summary as commit message
       ↓
Progress: "✅ New commit message: Refactor authentication system to improve security..."
```

## Branch Name Modification

Users can also override the branch name:

```json
{
  "user_response": "push to feature/caching-optimization"
}
```

The orchestrator will:
1. **Extract** branch name from LLM's `modifications` field
2. **Parse** using heuristics: `"branch name: <branch>"`
3. **Store** in `state.confirmation_data["branch_override"]`
4. **Create** the custom branch instead of default `repoai/{session_id}`

## LLM Decision Confidence

The LLM returns a confidence score (0.0-1.0) with each decision:

- **≥ 0.7** → Decision is accepted
- **< 0.7** → Action is overridden to `"clarify"`, orchestrator asks for clarification

```python
if result.confidence < 0.7:
    logger.warning(f"Low confidence push decision ({result.confidence:.2f})")
    result.action = "clarify"  # Override to ask for clarification
```

## Error Handling

### Parsing Errors

If the LLM fails to parse the response:

```python
return OrchestratorDecision(
    action="clarify",
    reasoning=f"Failed to parse push response due to error: {str(e)}",
    confidence=0.0,
)
```

### Missing Context

If code_changes or validation_result are missing when regenerating:

```python
logger.warning("Cannot regenerate commit message: missing code_changes or validation_result")
self._send_progress("⚠️  Cannot regenerate commit message, using original")
```

## Implementation Details

### `_interpret_push_intent()` Method

**Location:** `src/repoai/orchestrator/orchestrator_agent.py`

**Signature:**
```python
async def _interpret_push_intent(
    self, 
    user_response: str, 
    push_summary: str
) -> OrchestratorDecision:
```

**Prompt Structure:**
```python
prompt = f"""**Push Summary:**
{push_summary}

**User Response:**
"{user_response}"

{push_intent_instructions}

Analyze the user's response and determine if they approve or cancel the push."""
```

**LLM Configuration:**
- **Model Role:** `ModelRole.ORCHESTRATOR`
- **Temperature:** `0.2` (low for consistent decisions)
- **Max Tokens:** `512` (enough for decision + reasoning)
- **Schema:** `OrchestratorDecision`

### `_wait_for_push_confirmation()` Method

**Enhanced Features:**
1. **Natural language detection:** Checks for `"user_response"` field
2. **LLM interpretation:** Calls `_interpret_push_intent()` if natural language
3. **Override extraction:** Parses `modifications` for commit message/branch
4. **PR narrator integration:** Regenerates commit message if requested
5. **Backward compatibility:** Still accepts structured `{"action": "approve"}`

## Benefits

### For Users
- ✅ **Natural interaction** - No need to remember JSON structure
- ✅ **Flexible responses** - Multiple ways to say the same thing
- ✅ **Smart interpretation** - LLM understands intent
- ✅ **Easy customization** - Inline commit message/branch override

### For Developers
- ✅ **Consistent UX** - Same as plan confirmation
- ✅ **Backward compatible** - Structured format still works
- ✅ **Extensible** - Easy to add more intents
- ✅ **Type-safe** - Full mypy coverage

## Testing

### Manual Testing

```bash
# Test natural language approval
curl -X POST http://localhost:8000/api/v1/refactor/session_123/confirm-push \
  -H "Content-Type: application/json" \
  -d '{"user_response": "yes, looks good"}'

# Test commit message override
curl -X POST http://localhost:8000/api/v1/refactor/session_123/confirm-push \
  -H "Content-Type: application/json" \
  -d '{"user_response": "push with message: Fix authentication bug"}'

# Test commit message regeneration
curl -X POST http://localhost:8000/api/v1/refactor/session_123/confirm-push \
  -H "Content-Type: application/json" \
  -d '{"user_response": "yes but regenerate the commit message"}'

# Test branch override
curl -X POST http://localhost:8000/api/v1/refactor/session_123/confirm-push \
  -H "Content-Type: application/json" \
  -d '{"user_response": "push to feature/optimization"}'

# Test cancellation
curl -X POST http://localhost:8000/api/v1/refactor/session_123/confirm-push \
  -H "Content-Type: application/json" \
  -d '{"user_response": "no, cancel"}'
```

## Future Enhancements

### 1. **More Sophisticated Extraction**
- Use LLM to extract branch names more reliably
- Support multiple modifications in one response
- Handle complex instructions: "push to dev/feature with message X"

### 2. **Contextual Suggestions**
- LLM suggests better commit messages based on changes
- Branch name suggestions based on change type
- Validation of branch naming conventions

### 3. **Multi-turn Conversation**
- Ask follow-up questions if unclear
- Suggest improvements to user's commit message
- Confirm extracted overrides with user

### 4. **Audit Trail**
- Log all LLM interpretations with reasoning
- Track confidence scores over time
- Analyze common misinterpretations

## Comparison: Plan vs Push Confirmation

| Feature | Plan Confirmation | Push Confirmation |
|---------|-------------------|-------------------|
| Natural language | ✅ Yes | ✅ Yes (NEW) |
| LLM interpretation | ✅ Yes | ✅ Yes (NEW) |
| Modifications | ✅ Plan changes | ✅ Commit message/branch |
| Clarification | ✅ Yes | ✅ Yes (NEW) |
| Confidence threshold | 0.5 | 0.7 (stricter) |
| Regeneration support | ❌ No | ✅ Yes (PR narrator) |

## Conclusion

The push confirmation system now provides a **consistent, natural language interface** for users to approve/cancel git operations. The LLM intelligently interprets user intent and can even **regenerate commit messages** using the PR narrator agent when requested.

This creates a seamless, conversational experience for the entire RepoAI pipeline! 🚀
