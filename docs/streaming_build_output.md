# Streaming Maven/Gradle Build Output to Users

**Created**: 2024-11-13  
**Feature**: Real-time terminal output streaming during compilation and testing

---

## Problem Statement

Currently, when the Validator Agent runs Maven/Gradle compilation and tests:
- Users see: `"🔨 Compiling Java project..."` 
- Then wait 30-60 seconds with no feedback
- Then see: `"✅ Compilation passed"` or `"❌ Compilation failed: X errors"`

**Users cannot see**:
- Maven downloading dependencies
- Compilation progress (`[INFO] Compiling 45 source files`)
- Test execution output (`Running com.example.UserServiceTest`)
- Real-time errors as they occur

This creates a **"black box"** experience during validation.

---

## Solution Architecture

### Overview

Stream Maven/Gradle terminal output **line-by-line** to the frontend via SSE:

```
Maven/Gradle Process
     ↓ (stdout/stderr line-by-line)
java_build_utils.py (progress_callback)
     ↓
Validator Agent Tool
     ↓
Orchestrator._send_progress()
     ↓
SSE Event Stream
     ↓
Frontend Terminal Display
```

### Key Components

1. **`java_build_utils.py`**: Add `progress_callback` parameter to compilation/test functions
2. **Validator Agent**: Pass callback to build utils
3. **Orchestrator**: Forward build output via SSE with `event_type="build_output"`
4. **Frontend**: Display in terminal-like component

---

## Implementation Plan

### Phase 1: Update `java_build_utils.py`

**File**: `src/repoai/utils/java_build_utils.py`

#### Add Progress Callback Type

```python
from typing import Callable, Awaitable

# Progress callback type: async function that receives output lines
ProgressCallback = Callable[[str], Awaitable[None]]
```

#### Modify `compile_java_project()` Function

**Before** (lines 295-305):
```python
result = subprocess.run(
    command,
    cwd=repo_path,
    capture_output=True,
    text=True,
    timeout=300,
)
```

**After**:
```python
async def compile_java_project(
    repo_path: Path,
    build_tool_info: BuildToolInfo | None = None,
    clean: bool = False,
    skip_tests: bool = True,
    progress_callback: ProgressCallback | None = None,  # NEW
) -> CompilationResult:
    """
    Compile Java project with optional real-time progress streaming.
    
    Args:
        progress_callback: Optional async callback to receive output lines
    """
    # ... (build command setup)
    
    # Use Popen for streaming output
    process = subprocess.Popen(
        command,
        cwd=repo_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Merge stderr into stdout
        text=True,
        bufsize=1,  # Line buffered
    )
    
    output_lines = []
    
    # Stream output line by line
    if process.stdout:
        async for line in _stream_process_output(process.stdout):
            output_lines.append(line)
            
            # Send to progress callback if provided
            if progress_callback:
                await progress_callback(line)
    
    # Wait for completion
    return_code = process.wait(timeout=300)
    
    # Parse errors from collected output
    full_output = "".join(output_lines)
    errors, warnings = _parse_build_output(full_output, build_tool_info.tool)
    
    # ... (return CompilationResult)
```

#### Add Helper Function for Streaming

```python
import asyncio

async def _stream_process_output(stdout) -> AsyncIterator[str]:
    """
    Asynchronously stream output from subprocess line by line.
    
    Args:
        stdout: subprocess.PIPE stdout stream
        
    Yields:
        Output lines as they arrive
    """
    loop = asyncio.get_event_loop()
    
    while True:
        # Read line in thread pool (avoid blocking)
        line = await loop.run_in_executor(None, stdout.readline)
        
        if not line:
            break
            
        yield line
```

#### Update `run_java_tests()` Similarly

```python
async def run_java_tests(
    repo_path: Path,
    build_tool_info: BuildToolInfo | None = None,
    test_class: str | None = None,
    progress_callback: ProgressCallback | None = None,  # NEW
) -> TestResult:
    """
    Run Java tests with optional real-time progress streaming.
    """
    # Same Popen approach as compilation
    process = subprocess.Popen(
        command,
        cwd=repo_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    
    output_lines = []
    
    if process.stdout:
        async for line in _stream_process_output(process.stdout):
            output_lines.append(line)
            
            if progress_callback:
                await progress_callback(line)
    
    # ... (rest of implementation)
```

---

### Phase 2: Update Validator Agent

**File**: `src/repoai/agents/validator_agent.py`

#### Add Progress Callback to Dependencies

**File**: `src/repoai/dependencies/base.py`

```python
@dataclass
class ValidatorDependencies:
    """Dependencies for Validator Agent."""
    
    code_changes: CodeChanges
    repository_path: str | None
    min_test_coverage: float = 0.7
    strict_mode: bool = False
    progress_callback: Callable[[str], Awaitable[None]] | None = None  # NEW
```

#### Update `check_compilation` Tool

**Before** (lines 175-180):
```python
compile_result = await compile_java_project(
    repo_path=repo_path,
    build_tool_info=build_info,
    clean=False,
    skip_tests=True,
)
```

**After**:
```python
# Create progress callback wrapper
async def on_build_output(line: str) -> None:
    """Forward build output to orchestrator."""
    if ctx.deps.progress_callback:
        await ctx.deps.progress_callback(line)

compile_result = await compile_java_project(
    repo_path=repo_path,
    build_tool_info=build_info,
    clean=False,
    skip_tests=True,
    progress_callback=on_build_output,  # NEW
)
```

#### Update `run_tests` Tool Similarly

```python
@agent.tool
async def run_tests(
    ctx: RunContext[ValidatorDependencies],
    test_class: str | None = None,
) -> dict[str, Any]:
    """Run Java tests with real-time output streaming."""
    
    # Create progress callback
    async def on_test_output(line: str) -> None:
        if ctx.deps.progress_callback:
            await ctx.deps.progress_callback(line)
    
    test_result = await run_java_tests(
        repo_path=repo_path,
        build_tool_info=build_info,
        test_class=test_class,
        progress_callback=on_test_output,  # NEW
    )
    
    # ... (rest of implementation)
```

---

### Phase 3: Update Orchestrator

**File**: `src/repoai/orchestrator/orchestrator_agent.py`

#### Create Build Output Callback

```python
async def _run_validation_stage(self) -> None:
    """Run Validator Agent with real-time build output streaming."""
    from repoai.agents.validator_agent import run_validator_agent
    from repoai.dependencies import ValidatorDependencies
    
    # ... (existing code)
    
    # Create progress callback for build output
    async def on_build_output(line: str) -> None:
        """Stream Maven/Gradle output to frontend."""
        # Send via SSE with special event type
        self._send_progress(
            message=line.rstrip(),  # Remove trailing newline
            event_type="build_output",
            additional_data={
                "output_type": "compilation",  # or "testing"
                "raw_line": line,
            }
        )
    
    # Prepare dependencies WITH callback
    validator_deps = ValidatorDependencies(
        code_changes=self.state.code_changes,
        repository_path=self.deps.repository_path,
        min_test_coverage=self.deps.min_test_coverage,
        strict_mode=self.deps.require_all_checks_pass,
        progress_callback=on_build_output,  # NEW
    )
    
    # Run Validator Agent
    validation_result, metadata = await run_validator_agent(
        self.state.code_changes, validator_deps, self.adapter
    )
    
    # ... (rest of existing code)
```

---

### Phase 4: Frontend Implementation

**File**: `frontend/src/components/BuildOutputTerminal.tsx`

#### Terminal Component

```typescript
import React, { useEffect, useRef, useState } from 'react';
import { Terminal } from 'xterm';
import 'xterm/css/xterm.css';

interface BuildOutputTerminalProps {
  sessionId: string;
}

export const BuildOutputTerminal: React.FC<BuildOutputTerminalProps> = ({ sessionId }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Initialize xterm.js terminal
    if (terminalRef.current && !xtermRef.current) {
      xtermRef.current = new Terminal({
        theme: {
          background: '#1e1e1e',
          foreground: '#d4d4d4',
        },
        fontSize: 12,
        fontFamily: 'Menlo, Monaco, "Courier New", monospace',
        rows: 20,
      });
      
      xtermRef.current.open(terminalRef.current);
      xtermRef.current.writeln('Waiting for build output...');
    }

    // Connect to SSE stream
    const eventSource = new EventSource(`/api/v1/refactor/${sessionId}/stream`);

    eventSource.addEventListener('build_output', (event) => {
      const data = JSON.parse(event.data);
      const line = data.message;
      
      // Show terminal when build starts
      if (!isVisible) {
        setIsVisible(true);
      }
      
      // Write to terminal with color coding
      if (xtermRef.current) {
        // Color code based on content
        if (line.includes('ERROR') || line.includes('FAILED')) {
          xtermRef.current.writeln(`\x1b[31m${line}\x1b[0m`); // Red
        } else if (line.includes('WARNING')) {
          xtermRef.current.writeln(`\x1b[33m${line}\x1b[0m`); // Yellow
        } else if (line.includes('SUCCESS') || line.includes('BUILD SUCCESS')) {
          xtermRef.current.writeln(`\x1b[32m${line}\x1b[0m`); // Green
        } else if (line.includes('[INFO]')) {
          xtermRef.current.writeln(`\x1b[36m${line}\x1b[0m`); // Cyan
        } else {
          xtermRef.current.writeln(line);
        }
      }
    });

    return () => {
      eventSource.close();
      if (xtermRef.current) {
        xtermRef.current.dispose();
      }
    };
  }, [sessionId]);

  if (!isVisible) {
    return null;
  }

  return (
    <div className="build-output-terminal">
      <div className="terminal-header">
        <span>🔨 Build Output</span>
        <button onClick={() => setIsVisible(false)}>✕</button>
      </div>
      <div ref={terminalRef} className="terminal-container" />
    </div>
  );
};
```

#### Alternative: Simple Log Display

```typescript
export const BuildOutputLog: React.FC<{ sessionId: string }> = ({ sessionId }) => {
  const [lines, setLines] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const eventSource = new EventSource(`/api/v1/refactor/${sessionId}/stream`);

    eventSource.addEventListener('build_output', (event) => {
      const data = JSON.parse(event.data);
      setLines(prev => [...prev, data.message]);
      
      // Auto-scroll to bottom
      if (logRef.current) {
        logRef.current.scrollTop = logRef.current.scrollHeight;
      }
    });

    return () => eventSource.close();
  }, [sessionId]);

  return (
    <div className="build-log">
      <h3>Build Output</h3>
      <pre ref={logRef} className="log-content">
        {lines.map((line, i) => (
          <div key={i} className={getLineClass(line)}>
            {line}
          </div>
        ))}
      </pre>
    </div>
  );
};

function getLineClass(line: string): string {
  if (line.includes('ERROR') || line.includes('FAILED')) return 'log-error';
  if (line.includes('WARNING')) return 'log-warning';
  if (line.includes('SUCCESS')) return 'log-success';
  if (line.includes('[INFO]')) return 'log-info';
  return 'log-default';
}
```

---

## SSE Event Format

### Build Output Event

```json
{
  "type": "build_output",
  "event_type": "build_output",
  "status": "running",
  "stage": "validation",
  "message": "[INFO] Compiling 45 source files to target/classes",
  "data": {
    "output_type": "compilation",
    "raw_line": "[INFO] Compiling 45 source files to target/classes\n"
  },
  "timestamp": "2024-11-13T14:30:45.123Z"
}
```

### Example Stream Sequence

```javascript
// User sees these in real-time as Maven runs:

event: build_output
data: {"message": "[INFO] Scanning for projects...", ...}

event: build_output
data: {"message": "[INFO] Building spring-boot-app 1.0.0", ...}

event: build_output
data: {"message": "[INFO] --- maven-compiler-plugin:3.11.0:compile ---", ...}

event: build_output
data: {"message": "[INFO] Compiling 45 source files", ...}

event: build_output
data: {"message": "[ERROR] /src/Main.java:[10,5] cannot find symbol", ...}

event: progress
data: {"message": "❌ Compilation failed: 1 error", ...}
```

---

## User Experience

### Before (Current)

```
User submits refactoring request
     ↓
[Transformation completes]
     ↓
"🔨 Compiling Java project..."
     ↓
[30-60 second wait - NO FEEDBACK]
     ↓
"✅ Compilation passed" or "❌ Failed: X errors"
```

### After (With Streaming)

```
User submits refactoring request
     ↓
[Transformation completes]
     ↓
"🔨 Starting compilation..."
     ↓
TERMINAL SHOWS:
  [INFO] Scanning for projects...
  [INFO] Building spring-boot-app 1.0.0
  [INFO] Downloading: org.springframework.boot:...
  [INFO] Downloaded: 2.5 MB (10 seconds)
  [INFO] --- maven-compiler-plugin:3.11.0:compile ---
  [INFO] Compiling 45 source files to target/classes
  [INFO] ---------------------------------------------------------
  [INFO] BUILD SUCCESS
  [INFO] Total time: 42.3 s
     ↓
"✅ Compilation passed"
```

### Benefits

1. **Transparency**: Users see exactly what's happening
2. **Progress Indicators**: Know if Maven is downloading dependencies vs compiling
3. **Immediate Error Visibility**: See compilation errors as they occur
4. **Confidence**: Understand why compilation takes time
5. **Debugging**: Identify bottlenecks (e.g., slow dependency downloads)

---

## Configuration Options

### Enable/Disable Streaming

Add to `RefactorRequest` model:

```python
stream_build_output: bool = Field(
    default=True,
    description="Whether to stream Maven/Gradle output to frontend"
)
```

### Output Filtering

Filter noisy lines in `on_build_output`:

```python
async def on_build_output(line: str) -> None:
    """Stream Maven/Gradle output with optional filtering."""
    
    # Skip noisy lines
    skip_patterns = [
        "Progress (1):",  # Download progress bars
        "Downloaded from",  # Each download completion
    ]
    
    if any(pattern in line for pattern in skip_patterns):
        return  # Don't stream this line
    
    # Stream important lines
    self._send_progress(
        message=line.rstrip(),
        event_type="build_output",
        additional_data={"output_type": "compilation"}
    )
```

### Rate Limiting

Prevent overwhelming frontend with too many events:

```python
from asyncio import Lock
import time

class BuildOutputThrottle:
    """Throttle build output to prevent overwhelming frontend."""
    
    def __init__(self, max_lines_per_second: int = 50):
        self.max_lines_per_second = max_lines_per_second
        self.last_send_time = 0.0
        self.line_count = 0
        self.lock = Lock()
    
    async def should_send(self) -> bool:
        """Check if we should send the next line."""
        async with self.lock:
            current_time = time.time()
            
            # Reset counter every second
            if current_time - self.last_send_time >= 1.0:
                self.last_send_time = current_time
                self.line_count = 0
            
            # Check rate limit
            if self.line_count >= self.max_lines_per_second:
                return False  # Throttled
            
            self.line_count += 1
            return True

# Usage in orchestrator
self.build_throttle = BuildOutputThrottle(max_lines_per_second=50)

async def on_build_output(line: str) -> None:
    if await self.build_throttle.should_send():
        self._send_progress(
            message=line.rstrip(),
            event_type="build_output"
        )
```

---

## Testing

### Unit Tests

**File**: `tests/test_java_build_utils_streaming.py`

```python
import pytest
import asyncio
from pathlib import Path
from repoai.utils.java_build_utils import compile_java_project

@pytest.mark.asyncio
async def test_compilation_with_progress_callback(tmp_path):
    """Test that progress callback receives output lines."""
    
    # Create simple Java project
    src_dir = tmp_path / "src" / "main" / "java"
    src_dir.mkdir(parents=True)
    
    (src_dir / "Main.java").write_text("""
        public class Main {
            public static void main(String[] args) {
                System.out.println("Hello");
            }
        }
    """)
    
    # Create pom.xml
    (tmp_path / "pom.xml").write_text("""
        <project>
            <modelVersion>4.0.0</modelVersion>
            <groupId>com.test</groupId>
            <artifactId>test</artifactId>
            <version>1.0</version>
        </project>
    """)
    
    # Collect output lines
    output_lines = []
    
    async def progress_callback(line: str):
        output_lines.append(line)
    
    # Run compilation with callback
    result = await compile_java_project(
        repo_path=tmp_path,
        progress_callback=progress_callback
    )
    
    # Verify callback received output
    assert len(output_lines) > 0
    assert any("[INFO]" in line for line in output_lines)
    assert result.success
```

### Integration Test

**File**: `tests/integration/test_build_output_streaming.py`

```python
@pytest.mark.asyncio
async def test_full_validation_with_streaming(test_repo):
    """Test complete validation flow with build output streaming."""
    
    # Track streamed output
    build_output = []
    
    async def on_progress(event):
        if event.get("event_type") == "build_output":
            build_output.append(event["message"])
    
    # Run refactoring with streaming enabled
    session_id = await start_refactoring(
        user_prompt="Add logging",
        repo_url=test_repo,
        progress_callback=on_progress
    )
    
    # Wait for completion
    await wait_for_completion(session_id)
    
    # Verify build output was streamed
    assert len(build_output) > 10  # At least 10 lines
    assert any("Compiling" in line for line in build_output)
    assert any("[INFO]" in line for line in build_output)
```

---

## Performance Considerations

### Memory Usage

Streaming output prevents accumulating large buffers:
- **Before**: All output collected in memory, then returned
- **After**: Lines streamed immediately, no buffering

### Latency

Real-time streaming adds minimal overhead:
- Line-by-line processing: ~0.1-0.5ms per line
- SSE transmission: ~1-5ms per event
- Total overhead: <1% of build time

### Network Bandwidth

Typical Maven build output:
- ~500-2000 lines
- ~50-200 KB total
- ~1-4 KB/second during active compilation
- **Negligible** compared to code transfer

---

## Alternative Approaches

### 1. Batch Streaming (Every N Lines)

```python
output_buffer = []
BATCH_SIZE = 10

async def on_build_output(line: str):
    output_buffer.append(line)
    
    if len(output_buffer) >= BATCH_SIZE:
        # Send batch
        self._send_progress(
            message="\n".join(output_buffer),
            event_type="build_output"
        )
        output_buffer.clear()
```

**Pros**: Fewer SSE events  
**Cons**: Less real-time feel

### 2. Summary-Only Mode

Don't stream every line, just important events:

```python
async def on_build_output(line: str):
    # Only stream important lines
    if any(keyword in line for keyword in [
        "BUILD SUCCESS",
        "BUILD FAILURE",
        "ERROR",
        "Compiling",
        "Tests run:",
    ]):
        self._send_progress(message=line, event_type="build_output")
```

**Pros**: Less noise  
**Cons**: Less transparency

### 3. WebSocket Instead of SSE

Use bidirectional WebSocket for build output:

**Pros**: Lower latency, bidirectional  
**Cons**: More complex, already using SSE for other events

---

## Summary

### What Users Will See

```
📝 Stage 4: Validating changes...

🔨 Build Output ────────────────────────────
[INFO] Scanning for projects...
[INFO] Building spring-boot-app 1.0.0-SNAPSHOT
[INFO] -----------------------------------------------
[INFO] --- maven-compiler-plugin:3.11.0:compile ---
[INFO] Compiling 45 source files to target/classes
[INFO] -----------------------------------------------
[INFO] BUILD SUCCESS
[INFO] Total time: 42.321 s
────────────────────────────────────────────

✅ Compilation passed

🧪 Running tests...
────────────────────────────────────────────
[INFO] --- maven-surefire-plugin:3.0.0:test ---
[INFO] Running com.example.UserServiceTest
[INFO] Tests run: 12, Failures: 0, Errors: 0, Skipped: 0
────────────────────────────────────────────

✅ Tests passed (12/12)
✅ Validation completed successfully!
```

### Key Benefits

1. **Real-time visibility** into build process
2. **Immediate error detection** as they occur
3. **Build progress indicators** (downloading, compiling, testing)
4. **Professional user experience** matching IDE-like behavior
5. **Easy debugging** when builds fail

---

**Ready to implement!** This feature will significantly improve UX during the validation stage.
