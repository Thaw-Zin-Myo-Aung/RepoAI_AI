# RepoAI Demo Testing Guide - Postman

## 🎯 Overview
This guide walks you through testing the complete demo workflow with your private Java repository using Postman.

**Repository**: https://github.com/Thaw-Zin-Myo-Aung/Java-test (private)
**Demo Date**: November 17, 2025
**Testing Goal**: Verify all 3 demo features work end-to-end

---

## 📋 Prerequisites

### 1. Start the RepoAI API Server
```bash
cd /home/timmy/RepoAI/RepoAI_AI
uv run uvicorn src.repoai.api.main:app --reload --port 8000
```

### 2. Import Postman Collection
1. Open Postman
2. Click **Import** button
3. Select `RepoAI_Demo_Postman_Collection.json`
4. Collection will appear in your left sidebar

### 3. Configure Environment Variables
1. Click the collection name "RepoAI Demo Workflow"
2. Go to **Variables** tab
3. Set these variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `baseUrl` | `http://localhost:8000` | API server URL |
| `sessionId` | (leave empty) | Will be set after starting refactoring |

### 4. Update GitHub Token
In **each request** that needs authentication:
1. Go to **Body** → **raw**
2. Replace `YOUR_GITHUB_TOKEN_HERE` with your actual GitHub Personal Access Token
3. **Tip**: You can create a reusable environment variable for this too!

---

## 🧪 Testing Workflow

### **Phase 1: Test Conversational Intent (Greetings)** ✅

This tests that the orchestrator can handle greetings without starting the pipeline.

#### Test 1.1: Hello Greeting
**Request**: `1. Greeting Test → Test Hello Greeting`

**Request Body**:
```json
{
  "user_id": "demo_user",
  "user_prompt": "hello",
  "github_credentials": {
    "access_token": "YOUR_ACTUAL_TOKEN",
    "repository_url": "https://github.com/Thaw-Zin-Myo-Aung/Java-test",
    "branch": "main"
  },
  "mode": "interactive-detailed"
}
```

**Expected Response** (200 OK):
```json
{
  "session_id": "some-uuid",
  "status": "completed",
  "message": "Hello! I'm RepoAI, your intelligent code refactoring assistant..."
}
```

**What to Check**:
- ✅ Response is friendly and conversational
- ✅ Status is "completed" (not "waiting_for_confirmation")
- ✅ No pipeline starts (check server logs - should not see "Starting orchestrator")

#### Test 1.2: What Can You Do
**Request**: `1. Greeting Test → Test What Can You Do`

**Request Body**:
```json
{
  "user_id": "demo_user",
  "user_prompt": "what can you do?",
  "github_credentials": {
    "access_token": "YOUR_ACTUAL_TOKEN",
    "repository_url": "https://github.com/Thaw-Zin-Myo-Aung/Java-test",
    "branch": "main"
  },
  "mode": "interactive-detailed"
}
```

**Expected Response**: Explanation of capabilities (refactoring, code quality, etc.)

**What to Check**:
- ✅ Response explains features
- ✅ No pipeline starts

---

### **Phase 2: Start Refactoring Pipeline (SSE Streaming)** 🚀

This is the main test - you'll see real-time streaming of all events.

#### Test 2.1: Start Refactoring with Streaming
**Request**: `2. Start Refactoring Pipeline (SSE) → Start Refactoring with Streaming`

**Request Body**:
```json
{
  "user_id": "demo_user",
  "user_prompt": "refactor the code to improve readability and add comments",
  "github_credentials": {
    "access_token": "YOUR_ACTUAL_TOKEN",
    "repository_url": "https://github.com/Thaw-Zin-Myo-Aung/Java-test",
    "branch": "main"
  },
  "mode": "interactive-detailed"
}
```

**IMPORTANT Setup**:
1. Make sure **Accept** header is set to `text/event-stream`
2. Postman should show "EventSource" in the response

**Expected SSE Event Sequence**:

```
1. event: clone_start
   data: {"message": "Cloning repository..."}

2. event: clone_complete
   data: {"message": "Repository cloned successfully"}

3. event: intake_start
   data: {"message": "Analyzing repository structure..."}

4. event: intake_complete
   data: {"repository_info": {...}}

5. event: plan_request  ⚠️ STOP HERE - WAIT FOR YOUR CONFIRMATION
   data: {"plan": {...}, "session_id": "uuid-here"}

   ➡️ COPY the session_id value!
   ➡️ Go to collection Variables tab
   ➡️ Paste it as {{sessionId}} value
   ➡️ NOW proceed to Phase 3

... (pipeline continues after you confirm plan)

6. event: build_output  ⬅️ BUILD STREAMING DEMO!
   data: {"output": "[INFO] Scanning for projects..."}

7. event: build_output
   data: {"output": "[INFO] Building jar: ..."}

... (many build_output events - line by line streaming)

8. event: plan_complete
   data: {"message": "Plan execution completed"}

9. event: transform_start
   data: {"message": "Starting code transformation..."}

10. event: file_operation
    data: {"operation": "update", "path": "src/.../SomeClass.java", "content": "..."}

... (multiple file_operation events)

11. event: transform_complete
    data: {"message": "Transformation completed"}

12. event: validation_start
    data: {"message": "Validating changes..."}

13. event: build_output  ⬅️ VALIDATION BUILD STREAMING!
    data: {"output": "[INFO] Compiling validation build..."}

... (more build_output events)

14. event: validation_complete
    data: {"message": "Validation successful"}

15. event: push_request  ⚠️ STOP HERE - WAIT FOR YOUR CONFIRMATION
    data: {"message": "Commit message", "branch": "branch-name", "session_id": "..."}

    ➡️ NOW proceed to Phase 4

... (pipeline continues after you confirm push)

16. event: complete
    data: {"status": "success", "message": "Changes pushed successfully"}
```

**What to Check**:
- ✅ Events stream in real-time (not all at once)
- ✅ `build_output` events show line-by-line Maven/Gradle output
- ✅ Pipeline pauses at `plan_request` (waiting for you)
- ✅ `file_operation` events show actual file changes
- ✅ Pipeline pauses at `push_request` (waiting for you)

**Postman Tip**: 
- In Postman, SSE events will appear in the response body as they arrive
- You can see timestamps to verify they're streaming (not batched)

---

### **Phase 3: Confirm the Refactoring Plan** ✅

After receiving `plan_request` event, you need to confirm the plan.

**Prerequisites**:
1. ✅ You received the `plan_request` SSE event
2. ✅ You copied the `session_id` to collection variables
3. ✅ You reviewed the plan content

#### Option A: Structured Approval (Simple)
**Request**: `3. Plan Confirmation → Confirm Plan - Approve`

**Request Body**:
```json
{
  "session_id": "{{sessionId}}",
  "action": "approve"
}
```

**Expected Response** (200 OK):
```json
{
  "message": "Plan approved"
}
```

➡️ **Pipeline continues automatically** - go back to monitoring SSE stream!

---

#### Option B: Natural Language Approval (LLM Demo!) 🤖
**Request**: `3. Plan Confirmation → Confirm Plan - Natural Language Approve`

**Request Body**:
```json
{
  "session_id": "{{sessionId}}",
  "user_response": "yes, looks good!"
}
```

**Try Different Phrases**:
- "yes"
- "approve it"
- "go ahead"
- "looks great, proceed"
- "yep, do it"

**What to Check**:
- ✅ LLM correctly interprets your natural language as approval
- ✅ Pipeline continues after approval

---

#### Option C: Reject with Feedback (Regeneration Demo!)
**Request**: `3. Plan Confirmation → Confirm Plan - Reject with Reason`

**Request Body**:
```json
{
  "session_id": "{{sessionId}}",
  "user_response": "no, I want you to focus only on the UserService class and add more detailed javadoc comments"
}
```

**Expected Behavior**:
1. LLM extracts your feedback
2. Planner agent regenerates a new plan
3. You receive a NEW `plan_request` event with updated plan
4. You confirm the new plan

**What to Check**:
- ✅ LLM extracts modification request correctly
- ✅ New plan reflects your feedback
- ✅ Can iterate multiple times if needed

---

### **Phase 4: Confirm Push to GitHub** 🚀

After receiving `push_request` event, you need to confirm the push.

**Prerequisites**:
1. ✅ You received the `push_request` SSE event
2. ✅ Pipeline completed transformation and validation
3. ✅ You reviewed the commit message and branch name

#### Option A: Simple Approval
**Request**: `4. Push Confirmation → Confirm Push - Approve`

**Request Body**:
```json
{
  "session_id": "{{sessionId}}",
  "action": "approve"
}
```

**Expected Response**:
```json
{
  "message": "Push confirmed, committing and pushing changes..."
}
```

**What Happens**:
1. Changes are committed locally
2. Pushed to GitHub on the specified branch
3. You receive `complete` SSE event
4. **Go check your GitHub repo** - you should see a new branch with changes!

---

#### Option B: Natural Language Approval (LLM Demo!)
**Request**: `4. Push Confirmation → Confirm Push - Natural Language Approve`

**Request Body**:
```json
{
  "session_id": "{{sessionId}}",
  "user_response": "yes, push it!"
}
```

**Try Different Phrases**:
- "yes"
- "go ahead and push"
- "looks good"
- "approve"
- "do it"

---

#### Option C: Regenerate Commit Message (PR Narrator Demo!) 🤖
**Request**: `4. Push Confirmation → Confirm Push - Regenerate Commit Message`

**Request Body**:
```json
{
  "session_id": "{{sessionId}}",
  "user_response": "yes but please regenerate the commit message to be more detailed"
}
```

**Magic Keywords** (LLM detects):
- "regenerate"
- "rewrite"
- "improve"
- "better message"

**Expected Behavior**:
1. PR narrator agent analyzes the changes
2. Generates a new, more detailed commit message
3. You receive a NEW `push_request` event with updated message
4. You confirm the new message

**What to Check**:
- ✅ New commit message is more detailed/professional
- ✅ You can iterate multiple times

---

#### Option D: Custom Branch & Message (Advanced LLM Demo!)
**Request**: `4. Push Confirmation → Confirm Push - Custom Message & Branch`

**Request Body**:
```json
{
  "session_id": "{{sessionId}}",
  "user_response": "yes, push to branch 'feature/demo-test' with message 'Demo: Improved code readability and documentation'"
}
```

**Expected Behavior**:
1. LLM extracts branch name: `feature/demo-test`
2. LLM extracts commit message: `Demo: Improved code readability and documentation`
3. Pushes to your custom branch with your custom message

**What to Check**:
- ✅ Go to GitHub - verify branch name matches
- ✅ Go to GitHub - verify commit message matches
- ✅ LLM correctly parsed your natural language

---

#### Option E: Reject Push
**Request**: `4. Push Confirmation → Confirm Push - Reject`

**Request Body**:
```json
{
  "session_id": "{{sessionId}}",
  "action": "reject"
}
```

**Expected Behavior**:
- Changes remain local (not pushed)
- Pipeline ends gracefully
- Session marked as completed

---

### **Phase 5: Check Session Status (Optional)** 📊

You can check session status anytime during the pipeline.

**Request**: `5. Get Session Status → Check Session Status`

**URL**: `{{baseUrl}}/api/refactor/status/{{sessionId}}`

**Expected Response**:
```json
{
  "session_id": "uuid-here",
  "status": "waiting_for_confirmation",  // or "in_progress", "completed"
  "current_stage": "plan_confirmation",
  "repository_url": "...",
  "created_at": "2025-11-13T...",
  "updated_at": "2025-11-13T..."
}
```

**Use Cases**:
- Check if session is still active
- See which stage pipeline is at
- Debug if something went wrong

---

## 🎯 Complete Testing Checklist

### ✅ Conversational Intent
- [ ] Hello greeting returns friendly response
- [ ] "What can you do" explains capabilities
- [ ] No pipeline starts for greetings

### ✅ SSE Streaming
- [ ] Events arrive in real-time (not batched)
- [ ] `clone_start` → `clone_complete` events
- [ ] `intake_start` → `intake_complete` with repo info
- [ ] `plan_request` pauses and waits

### ✅ Build Output Streaming (KEY DEMO!)
- [ ] `build_output` events stream line-by-line
- [ ] Maven/Gradle output visible (e.g., "[INFO] Building jar...")
- [ ] Build output appears during plan execution
- [ ] Build output appears during validation

### ✅ Plan Confirmation
- [ ] Structured approval works (`action: "approve"`)
- [ ] Natural language approval works ("yes, looks good")
- [ ] Rejection with feedback regenerates plan
- [ ] Can iterate multiple times

### ✅ File Operations
- [ ] `file_operation` events show actual file changes
- [ ] File content is included in events
- [ ] Multiple files are updated

### ✅ Validation
- [ ] `validation_start` → `validation_complete` events
- [ ] Build output streams during validation
- [ ] Validation succeeds (or reports errors)

### ✅ Push Confirmation (KEY DEMO!)
- [ ] `push_request` includes commit message and branch
- [ ] Structured approval works
- [ ] Natural language approval works ("yes, push it")
- [ ] Regenerate commit message works (PR narrator)
- [ ] Custom branch/message works
- [ ] Rejection works

### ✅ GitHub Integration
- [ ] Changes are actually pushed to GitHub
- [ ] Branch name is correct
- [ ] Commit message is correct
- [ ] Can see changes in GitHub UI

---

## 🐛 Troubleshooting

### Issue: SSE Events Not Streaming
**Symptom**: All events arrive at once, not real-time

**Fix**:
1. Check `Accept: text/event-stream` header is set
2. Verify server logs show SSE connection
3. Try using cURL instead of Postman:
```bash
curl -N -H "Accept: text/event-stream" \
  -H "Content-Type: application/json" \
  -d '{"repository_url":"...","github_token":"...","user_request":"...","mode":"interactive-detailed"}' \
  http://localhost:8000/api/refactor/start
```

### Issue: Build Output Not Streaming
**Symptom**: No `build_output` events appear

**Fix**:
1. Check mode is `interactive-detailed` (not `non-interactive`)
2. Verify Java project has Maven/Gradle build
3. Check server logs for build errors

### Issue: 401 Unauthorized
**Symptom**: GitHub API returns 401

**Fix**:
1. Verify GitHub token is valid
2. Check token has repo access permissions
3. Verify repository URL is correct (private repo requires token)

### Issue: Session Not Found
**Symptom**: 404 when confirming plan/push

**Fix**:
1. Verify `session_id` is correctly copied to collection variable
2. Check session hasn't timed out (sessions expire after 30 minutes)
3. Check server logs for session creation

### Issue: Pipeline Hangs
**Symptom**: No more SSE events after certain point

**Fix**:
1. Check if pipeline is waiting for confirmation
2. Look for `plan_request` or `push_request` events
3. Send confirmation to continue
4. Check server logs for errors

---

## 📝 Server Logs to Monitor

While testing, watch the server terminal for:

```bash
# SSE connection established
INFO: SSE client connected for session: uuid-here

# Conversational intent detected
INFO: Conversational intent detected, responding without pipeline

# Build streaming
INFO: Streaming build output for session: uuid-here
INFO: Build output line: [INFO] Building jar...

# Waiting for confirmations
INFO: Waiting for plan confirmation for session: uuid-here
INFO: Waiting for push confirmation for session: uuid-here

# LLM interpretations
INFO: LLM interpreted plan confirmation as: approve
INFO: LLM interpreted push confirmation as: approve with regenerate

# Completions
INFO: Pipeline completed successfully for session: uuid-here
```

---

## 🎬 Demo Script (November 17)

### Act 1: Conversational (30 seconds)
1. Show greeting: "hello" → friendly response
2. Show capability: "what can you do?" → explains features

### Act 2: Refactoring Pipeline (3 minutes)
1. Start refactoring: "refactor code to improve readability"
2. **Show SSE streaming** - events appear real-time
3. **Show build output streaming** - Maven compilation line-by-line
4. Plan confirmation with natural language: "yes, looks good!"
5. **Show file operations streaming** - actual code changes
6. **Show validation build streaming** - compilation output again
7. Push confirmation with custom message: "yes, push to branch 'demo' with message 'Improved code quality'"
8. **Show GitHub** - branch and commit appear!

### Act 3: Advanced Features (2 minutes)
1. Start another refactoring
2. Reject plan: "no, focus on UserService class only"
3. Approve new plan
4. Request commit message regeneration: "yes but make the message better"
5. Approve regenerated message
6. Show final GitHub result

---

## 🚀 Next Steps

After Postman testing is successful:

1. **Day 3 (Nov 14-15)**: Frontend implementation
   - Terminal component for build output
   - Confirmation modals with natural language input
   - SSE streaming client

2. **Final Testing (Nov 16)**: End-to-end with frontend
   - Test complete workflow through UI
   - Fix any integration issues

3. **Demo Day (Nov 17)**: Present! 🎉

---

## 📞 Questions?

If you encounter any issues during testing, check:
1. Server logs (`uvicorn` output)
2. Postman console (View → Show Postman Console)
3. Network tab (check request/response details)

**Key Files to Check**:
- `/home/timmy/RepoAI/RepoAI_AI/src/repoai/api/routes/refactor.py`
- `/home/timmy/RepoAI/RepoAI_AI/src/repoai/orchestrator/orchestrator_agent.py`
- `/home/timmy/RepoAI/RepoAI_AI/src/repoai/utils/java_build_utils.py`

Good luck with testing! 🎯
