# 🎨 Frontend Diff Rendering Guide

## 📦 What Backend Sends

```json
{
  "event_type": "file_modified",
  "file_path": "src/main/java/com/example/SecurityConfig.java",
  "data": {
    "operation": "modified",
    "original_content": "package com.example.config;\n\nimport org.springframework.context.annotation.Configuration;\nimport org.springframework.security.config.annotation.web.builders.HttpSecurity;\n\n@Configuration\npublic class SecurityConfig {\n    protected void configure(HttpSecurity http) throws Exception {\n        http.authorizeRequests()\n            .anyRequest().permitAll();\n    }\n}",
    "modified_content": "package com.example.config;\n\nimport com.example.auth.JwtAuthenticationFilter;\nimport org.springframework.context.annotation.Bean;\nimport org.springframework.context.annotation.Configuration;\nimport org.springframework.security.config.annotation.web.builders.HttpSecurity;\nimport org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;\n\n@Configuration\npublic class SecurityConfig {\n    @Bean\n    public JwtAuthenticationFilter jwtAuthenticationFilter() {\n        return new JwtAuthenticationFilter();\n    }\n    \n    protected void configure(HttpSecurity http) throws Exception {\n        http.authorizeRequests()\n            .antMatchers(\"/api/public/**\").permitAll()\n            .anyRequest().authenticated()\n            .and()\n            .addFilterBefore(jwtAuthenticationFilter(), UsernamePasswordAuthenticationFilter.class);\n    }\n}",
    "diff": "@@ -1,10 +1,20 @@\n package com.example.config;\n \n+import com.example.auth.JwtAuthenticationFilter;\n+import org.springframework.context.annotation.Bean;\n import org.springframework.context.annotation.Configuration;\n import org.springframework.security.config.annotation.web.builders.HttpSecurity;\n+import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;\n \n @Configuration\n public class SecurityConfig {\n+    @Bean\n+    public JwtAuthenticationFilter jwtAuthenticationFilter() {\n+        return new JwtAuthenticationFilter();\n+    }\n+    \n     protected void configure(HttpSecurity http) throws Exception {\n         http.authorizeRequests()\n+            .antMatchers(\"/api/public/**\").permitAll()\n-            .anyRequest().permitAll();\n+            .anyRequest().authenticated()\n+            .and()\n+            .addFilterBefore(jwtAuthenticationFilter(), UsernamePasswordAuthenticationFilter.class);\n     }\n }",
    "lines_added": 12,
    "lines_removed": 5
  }
}
```

---

## 🛠️ **Option 1: Use JavaScript Diff Libraries** ⭐ RECOMMENDED

### **Best Libraries:**

#### **1. react-diff-viewer** (React)
- ✅ Beautiful side-by-side view
- ✅ Syntax highlighting
- ✅ Line-by-line comparison
- ✅ Easy to use

**Installation:**
```bash
npm install react-diff-viewer
```

**Usage:**
```jsx
import ReactDiffViewer from 'react-diff-viewer';

function FileComparisonModal({ fileChangeEvent }) {
  const oldCode = fileChangeEvent.data.original_content;
  const newCode = fileChangeEvent.data.modified_content;
  
  return (
    <div className="diff-modal">
      <h3>Modified: {fileChangeEvent.file_path}</h3>
      <p>Changes: +{fileChangeEvent.data.lines_added} / -{fileChangeEvent.data.lines_removed}</p>
      
      <ReactDiffViewer
        oldValue={oldCode}
        newValue={newCode}
        splitView={true}
        showDiffOnly={false}
        useDarkTheme={false}
        leftTitle="Before (Original)"
        rightTitle="After (Modified)"
        compareMethod="diffWords"  // or "diffLines"
      />
    </div>
  );
}
```

**Output:**
```
┌────────────────────────────────┬────────────────────────────────┐
│ Before (Original)              │ After (Modified)               │
├────────────────────────────────┼────────────────────────────────┤
│ package com.example.config;    │ package com.example.config;    │
│                                │                                │
│                                │ import com.example.auth.Jwt... │← GREEN
│                                │ import org.springframework...  │← GREEN
│ import org.springframework...  │ import org.springframework...  │
│ import org.springframework...  │ import org.springframework...  │
│                                │ import org.springframework...  │← GREEN
│                                │                                │
│ @Configuration                 │ @Configuration                 │
│ public class SecurityConfig {  │ public class SecurityConfig {  │
│                                │     @Bean                      │← GREEN
│                                │     public JwtAuthentication...│← GREEN
│                                │         return new JwtAuth...  │← GREEN
│                                │     }                          │← GREEN
│                                │                                │← GREEN
│     protected void configure...│     protected void configure...│
│         http.authorizeReque... │         http.authorizeReque... │
│             .anyRequest().per..│             .antMatchers("...  │← GREEN
│                                │             .anyRequest().aut..│← YELLOW (changed)
│                                │             .and()             │← GREEN
│                                │             .addFilterBefore...│← GREEN
│     }                          │     }                          │
│ }                              │ }                              │
└────────────────────────────────┴────────────────────────────────┘
```

---

#### **2. monaco-editor** (VS Code-like)
- ✅ Full VS Code editor experience
- ✅ Built-in diff viewer
- ✅ Syntax highlighting
- ✅ Professional look

**Installation:**
```bash
npm install @monaco-editor/react
```

**Usage:**
```jsx
import { DiffEditor } from '@monaco-editor/react';

function CodeDiffViewer({ fileChangeEvent }) {
  const oldCode = fileChangeEvent.data.original_content;
  const newCode = fileChangeEvent.data.modified_content;
  
  return (
    <DiffEditor
      height="600px"
      language="java"
      original={oldCode}
      modified={newCode}
      theme="vs-light"
      options={{
        renderSideBySide: true,
        readOnly: true,
        originalEditable: false,
        modifiedEditable: false,
      }}
    />
  );
}
```

**Output:** Looks exactly like VS Code diff view! 🎨

---

#### **3. diff2html** (Pure HTML/CSS)
- ✅ Works with any framework
- ✅ Beautiful rendering
- ✅ Can parse unified diff OR use full contents

**Installation:**
```bash
npm install diff2html
```

**Usage (with full contents):**
```javascript
import { Diff2Html } from 'diff2html';
import 'diff2html/bundles/css/diff2html.min.css';

function renderDiff(fileChangeEvent) {
  const oldCode = fileChangeEvent.data.original_content;
  const newCode = fileChangeEvent.data.modified_content;
  
  // Generate unified diff from two strings
  const diff = require('diff');
  const patch = diff.createPatch(
    fileChangeEvent.file_path,
    oldCode,
    newCode,
    'Before',
    'After'
  );
  
  // Render as HTML
  const diffHtml = Diff2Html.html(patch, {
    drawFileList: true,
    matching: 'lines',
    outputFormat: 'side-by-side'
  });
  
  document.getElementById('diff-container').innerHTML = diffHtml;
}
```

---

## 🔧 **Option 2: Use the Unified Diff String** (Harder)

If you want to use the `diff` field directly:

### **JavaScript Libraries that Parse Unified Diff:**

#### **1. diff** (Node.js library)
```bash
npm install diff
```

```javascript
import * as Diff from 'diff';

function parseDiff(diffString) {
  const parsedDiff = Diff.parsePatch(diffString);
  
  // parsedDiff contains:
  // - hunks: array of change blocks
  // - oldFileName, newFileName
  // - oldHeader, newHeader
  
  return parsedDiff;
}
```

#### **2. parse-diff**
```bash
npm install parse-diff
```

```javascript
import parseDiff from 'parse-diff';

function renderUnifiedDiff(unifiedDiffString) {
  const files = parseDiff(unifiedDiffString);
  
  files.forEach(file => {
    file.chunks.forEach(chunk => {
      chunk.changes.forEach(change => {
        if (change.type === 'add') {
          console.log(`+ ${change.content}`);  // GREEN
        } else if (change.type === 'del') {
          console.log(`- ${change.content}`);  // RED
        } else {
          console.log(`  ${change.content}`);  // GRAY
        }
      });
    });
  });
}
```

---

## ⭐ **RECOMMENDED APPROACH for Nov 17th Demo:**

### **Use Option 1: react-diff-viewer or monaco-editor**

**Why?**
1. ✅ **Already have both full contents** (`original_content` + `modified_content`)
2. ✅ **No parsing needed** - just pass strings directly
3. ✅ **Beautiful UI out-of-the-box**
4. ✅ **Syntax highlighting included**
5. ✅ **Side-by-side view**
6. ✅ **Fast implementation** (< 1 hour)

---

## 📝 **Complete React Component Example:**

```jsx
import React, { useEffect, useState } from 'react';
import ReactDiffViewer from 'react-diff-viewer';

function FileChangesFeed({ sessionId }) {
  const [fileChanges, setFileChanges] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);

  useEffect(() => {
    // Connect to SSE
    const eventSource = new EventSource(
      `http://localhost:8000/api/sessions/${sessionId}/sse`
    );

    eventSource.addEventListener('file_created', (event) => {
      const data = JSON.parse(event.data);
      setFileChanges(prev => [...prev, { type: 'created', ...data }]);
    });

    eventSource.addEventListener('file_modified', (event) => {
      const data = JSON.parse(event.data);
      setFileChanges(prev => [...prev, { type: 'modified', ...data }]);
    });

    eventSource.addEventListener('file_deleted', (event) => {
      const data = JSON.parse(event.data);
      setFileChanges(prev => [...prev, { type: 'deleted', ...data }]);
    });

    return () => eventSource.close();
  }, [sessionId]);

  return (
    <div className="file-changes-container">
      {/* File List */}
      <div className="file-list">
        <h3>Code Changes ({fileChanges.length} files)</h3>
        {fileChanges.map((change, idx) => (
          <div
            key={idx}
            className={`file-item ${change.type}`}
            onClick={() => setSelectedFile(change)}
          >
            <span className="icon">
              {change.type === 'created' && '📝'}
              {change.type === 'modified' && '✏️'}
              {change.type === 'deleted' && '🗑️'}
            </span>
            <span className="filename">{change.file_path}</span>
            <span className="stats">
              +{change.data.lines_added} / -{change.data.lines_removed}
            </span>
          </div>
        ))}
      </div>

      {/* Diff Viewer */}
      {selectedFile && (
        <div className="diff-viewer">
          <h3>{selectedFile.file_path}</h3>
          
          {selectedFile.type === 'created' && (
            <div>
              <h4>New File Created (+{selectedFile.data.lines_added} lines)</h4>
              <pre className="code-block">
                {selectedFile.data.modified_content}
              </pre>
            </div>
          )}

          {selectedFile.type === 'modified' && (
            <div>
              <h4>File Modified 
                (+{selectedFile.data.lines_added} / -{selectedFile.data.lines_removed})
              </h4>
              <ReactDiffViewer
                oldValue={selectedFile.data.original_content}
                newValue={selectedFile.data.modified_content}
                splitView={true}
                leftTitle="Before"
                rightTitle="After"
                compareMethod="diffLines"
                styles={{
                  variables: {
                    light: {
                      diffViewerBackground: '#fff',
                      addedBackground: '#e6ffed',
                      removedBackground: '#ffeef0',
                    }
                  }
                }}
              />
            </div>
          )}

          {selectedFile.type === 'deleted' && (
            <div>
              <h4>File Deleted (-{selectedFile.data.lines_removed} lines)</h4>
              <p className="warning">⚠️ This file will be permanently removed</p>
              <pre className="code-block deleted">
                {selectedFile.data.original_content}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default FileChangesFeed;
```

**CSS:**
```css
.file-changes-container {
  display: flex;
  height: 100vh;
}

.file-list {
  width: 300px;
  border-right: 1px solid #ddd;
  overflow-y: auto;
}

.file-item {
  padding: 12px;
  cursor: pointer;
  border-bottom: 1px solid #eee;
}

.file-item:hover {
  background-color: #f5f5f5;
}

.file-item.created { border-left: 4px solid #28a745; }
.file-item.modified { border-left: 4px solid #ffc107; }
.file-item.deleted { border-left: 4px solid #dc3545; }

.diff-viewer {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.code-block {
  background: #f6f8fa;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'Courier New', monospace;
}

.code-block.deleted {
  background: #ffeef0;
  border: 1px solid #dc3545;
}
```

---

## 🎯 **Answer to Your Question:**

### **Is the unified diff easy to render?**

**Short answer:** Not directly, but you have better options!

**Best approach:**
1. ✅ Use `original_content` and `modified_content` (already provided)
2. ✅ Use react-diff-viewer or monaco-editor
3. ✅ Library handles all rendering
4. ✅ Beautiful side-by-side view
5. ✅ Syntax highlighting included
6. ✅ Implementation time: < 1 hour

**Unified diff string is useful for:**
- Git-like views
- Copy/paste for developers
- Archival purposes
- But NOT required for rendering!

---

## 🚀 **For Nov 17th Demo:**

### **Recommended Implementation:**

```bash
# Install
npm install react-diff-viewer

# Use in component (copy-paste from above)
# Works immediately!
```

**Demo Flow:**
1. User submits refactor request
2. Files appear in left sidebar as they're generated
3. Click on a file → See full diff on right
4. For new files → Show full content with syntax highlighting
5. For modified files → Show beautiful side-by-side comparison
6. For deleted files → Show warning + content being removed

**Total implementation time:** 2-3 hours including styling! 🎉

The unified diff string is **bonus data** - you don't need to parse it. Just use the full contents with a diff library!
