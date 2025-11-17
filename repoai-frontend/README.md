# Repo-AI-Frontend

A modern React-based frontend application for AI-powered repository analysis and code assistance. This project provides an intuitive interface for chatting with AI about your codebase, viewing code changes, and managing repository operations.

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Development](#development)
- [Environment Variables](#environment-variables)
- [API Layer and Hooks](#api-layer-and-hooks)
- [Contributing](#contributing)

## Features

- *AI Chat Interface*: Real-time chat with AI for code analysis and assistance
- *Repository Management*: Browse and manage repositories with OAuth authentication
- *Code Diff Viewer*: Visual file change viewer for code modifications
- *Git Operations*: Support for commits, branching, and git operations
- *Summary Cards*: View plan summaries, push summaries, and validation results
- *Terminal Console*: Interactive terminal output display
- *Conversation History*: Track and manage chat conversations
- *User Profile*: Manage user settings and preferences
- *Responsive Design*: Mobile-friendly UI built with Tailwind CSS

## Project Structure

src/
├── components/          # Reusable React components
│   ├── ChatContent.jsx
│   ├── ChatInput.jsx
│   ├── ChatMessages.jsx
│   ├── FileChangeViewer.jsx
│   ├── ClearHistoryModal.jsx
│   ├── PlanSummaryCard.jsx
│   ├── PushSummaryCard.jsx
│   ├── ValidationSummaryCard.jsx
│   ├── TerminalConsole.jsx
│   ├── RequireAuth.jsx
│   └── Sidebar.jsx
├── pages/               # Page components
│   ├── ChatBox.jsx
│   ├── ChatHistory.jsx
│   ├── ChatHistoryDetail.jsx
│   ├── Commit.jsx
│   ├── Home.jsx
│   ├── Login.jsx
│   ├── Profile.jsx
│   ├── Preview.jsx
│   └── Loading.jsx
├── libs/                # Core libraries and hooks
│   ├── api/             # API utilities and endpoints
│   ├── hooks/           # React Query hooks organized by feature
│   ├── stores/          # Zustand stores for state management
│   └── utils/           # Helper utilities
├── styles/              # CSS stylesheets
├── assets/              # Static assets
└── App.jsx             # Main app component


## Installation

### Prerequisites

- Node.js 16+ 
- npm or yarn package manager

### Setup Steps

1. *Clone the repository*
   
   git clone https://github.com/Thuraung-hub/Repo-AI-Frontend.git
   cd Repo-AI-Frontend
   

2. *Install dependencies*
   
   npm install
   # or
   yarn install
   

3. *Create environment configuration*
   
   cp .env.example .env.local  # if available
   # or manually create .env.local (see Configuration section)
   

4. *Start development server*
   
   npm run dev
   # or
   yarn dev
   

   The app will open at http://localhost:5173 (Vite default)

## Configuration

### Environment variables

Create a .env.local file in the project root with at least:

- VITE_API_BASE_URL: Base URL of your backend API (no trailing slash). Example:
	- VITE_API_BASE_URL=http://localhost:8081
- Optional: VITE_LOGIN_URL: Full URL to initiate OAuth login (used by Login page). Example:
	- VITE_LOGIN_URL=http://localhost:8081/api/auth/login
- Optional: VITE_AUTH_REDIRECT_URL: Client-side login page to redirect on 401 responses. Example:
	- VITE_AUTH_REDIRECT_URL=http://localhost:3000/login

Notes:
- All API requests are automatically sent to ${VITE_API_BASE_URL}/route/<endpoint>.
- 401 Unauthorized responses trigger a redirect to VITE_AUTH_REDIRECT_URL (fallback to http://localhost:3000/login).
- The Login page redirects the browser to VITE_LOGIN_URL (fallback to http://localhost:8081/api/auth/login).

## API Layer and Hooks

- Central API utilities live in src/libs/api/api.js.
- Endpoints are centralized in src/libs/api/endpoints.js.
- Use React Query hooks from api.js:
	- useGetQuery(endpoint, params?, options?) for GET requests
	- usePost|usePut|usePatch|useDelete(endpoint, options?) for write operations

Example:

import { useGetQuery } from './libs/api/api';
import { ENDPOINTS } from './libs/api/endpoints';

const { data, isLoading, error } = useGetQuery(ENDPOINTS.USER);

## Usage

### Authentication

1. Navigate to the Login page
2. Click "Login with OAuth" to authenticate via the configured OAuth provider
3. You'll be redirected back to the application upon successful authentication
4. Your session is maintained via stored auth tokens

### Chat Interface

1. *Start a Conversation*: Click "New Chat" to initiate an AI conversation
2. *Send Messages*: Type your message in the input field and press Enter or click Send
3. *View History*: Access previous conversations from the Chat History page
4. *Clear History*: Use the "Clear History" modal to remove conversation records

### Repository Management

1. *Select Repository*: Choose a repository from the sidebar
2. *View Changes*: Navigate to the Preview page to see file diffs
3. *Commit Changes*: Use the Commit page to review and commit changes

### Terminal Console

View command outputs and logs in the TerminalConsole component for debugging and monitoring.

## Development

### Available Scripts

- npm run dev - Start development server with hot reload
- npm run build - Build for production
- npm run preview - Preview production build locally
- npm run lint - Run ESLint (if configured)

### Key Technologies

- *React 18* - UI library
- *Vite* - Build tool and dev server
- *React Query* - Server state management
- *Zustand* - Client state management
- *Tailwind CSS* - Utility-first CSS framework
- *Axios* - HTTP client

### State Management

*Zustand Stores* (src/libs/stores/)
- useSession - Authentication and session state
- useUser - User profile information
- useCounterStore - Application-wide counters

*React Query* (src/libs/hooks/)
- Organized by feature (auth, branches, chat, conversations, profile, repoai, repos)
- Provides queries and mutations for server-side data

### Adding New Features

1. *Create API endpoint* in src/libs/api/endpoints.js
2. *Add hooks* in appropriate src/libs/hooks/{feature}/ directory
3. *Build component* in src/components/ or src/pages/
4. *Add styles* in src/styles/
5. *Test locally* with npm run dev

### Debugging

- Use React Developer Tools extension for component inspection
- Check Network tab in DevTools for API requests
- Use console.log() or debugger for troubleshooting
- Review terminal output for build/compilation errors

## Contributing

### Guidelines

1. *Fork the repository* and create a feature branch
   
   git checkout -b feature/your-feature-name
   

2. *Follow code style*: Ensure consistent formatting with project standards
   - Use meaningful variable and function names
   - Keep components focused and single-responsibility
   - Comment complex logic

3. *Test your changes*
   
   npm run dev
   # Test thoroughly in the browser
   

4. *Commit with clear messages*
   
   git commit -m "feat: add new feature description"
   

5. *Push to your fork*
   
   git push origin feature/your-feature-name
   

6. *Create a Pull Request* with a clear description of changes

### Code Quality

- Keep component files under 300 lines where possible
- Extract reusable logic into custom hooks
- Use proper error handling and validation
- Add loading and error states for async operations

### Reporting Issues

When reporting issues, please include:
- Clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Screenshots or error logs if applicable

## License

[Add your license information here]

## Support

For questions or issues, please:
- Open an issue on GitHub
- Contact the maintainers
- Check existing documentation

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for version history and updates.