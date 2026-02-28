# OpenClaw Guardian - Automated GitHub Dependency Updater

## Table of Contents

1. [Project Overview](#project-overview)
2. [The Idea](#the-idea)
3. [Features](#features)
4. [How It Works](#how-it-works)
5. [Project Structure](#project-structure)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Usage](#usage)
9. [Technical Details](#technical-details)
10. [Architecture](#architecture)
11. [Workflow](#workflow)
12. [API Requirements](#api-requirements)

---

## Project Overview

**OpenClaw Guardian** is an autonomous AI agent designed to automatically monitor GitHub repositories for outdated npm dependencies, upgrade them to their latest versions, and create pull requests with the changes. The project was built for the OpenClaw hackathon and demonstrates real-world autonomy, multi-step reasoning, persistent memory, and tool usage with external APIs.

The agent operates as a continuous loop that periodically checks the configured repository for outdated packages. When it finds packages that need updating, it performs a complete workflow: cloning the repository, checking for outdated dependencies, upgrading them to the latest versions, committing the changes, pushing a new branch, and creating a pull request on GitHub.

---

## The Idea

The idea behind OpenClaw Guardian stems from a common problem faced by developers: keeping dependencies up-to-date is time-consuming and often overlooked. Outdated dependencies can lead to security vulnerabilities, compatibility issues, and missing out on performance improvements and new features.

Traditional approaches to dependency management require manual intervention or CI/CD pipelines that only run during deployments. OpenClaw Guardian takes a proactive approach by acting as an autonomous agent that continuously monitors repositories and automatically proposes updates through pull requests.

This approach offers several advantages. First, it ensures repositories stay current without requiring developer time for routine updates. Second, by creating pull requests, it allows developers to review changes before merging, maintaining control over the update process. Third, the agent saves upgrade details in memory so the frontend can display what packages were upgraded and when.

The core concept is to create a "set it and forget it" system that handles dependency maintenance automatically while keeping humans in the loop through code review via pull requests.

---

## Features

OpenClaw Guardian comes with a comprehensive set of features that make it a powerful tool for automated dependency management:

### Core Features

- **Automated Dependency Checking**: Uses `npm outdated` to identify packages that have newer versions available
- **Smart Package Upgrading**: Upgrades packages to their absolute latest versions using `npm install package@latest`
- **Automatic Git Branch Creation**: Creates a new branch for each upgrade cycle with a unique timestamp
- **Pull Request Creation**: Automatically creates pull requests via the GitHub API for code review
- **Memory Tracking**: Saves details of upgraded packages so the frontend can display what was upgraded and the results after each cycle
- **Configurable Check Interval**: Runs continuously on a configurable schedule (default: every hour)
- **Detailed Logging**: Provides comprehensive logging to both console and file for debugging and auditing

### Advanced Features

- **Session-Based Memory**: Each time you save new configuration or reload the page, the previous memory and repo details are cleared for a fresh start
- **Repository Cleanup**: Automatically deletes cloned repositories after each cycle to keep the system clean
- **Backup and Rollback**: Creates backups of package.json before upgrading and can restore if issues occur
- **Git Configuration**: Automatically configures git user identity for commits

---

## How It Works

OpenClaw Guardian operates through a carefully designed workflow that ensures reliable and consistent dependency updates:

1. **Initialization**: The agent loads configuration from config.yaml, sets up logging, and initializes all skill modules including the repository monitor, dependency checker, upgrade executor, PR creator, and memory manager.

2. **Repository Cloning**: On each cycle, the agent clones the configured GitHub repository fresh. It always removes any existing clone to ensure a clean state.

3. **Dependency Installation**: After cloning, the agent runs `npm install` to ensure all dependencies are properly installed before checking for outdated packages.

4. **Outdated Package Detection**: The agent runs `npm outdated --json` to get a list of all packages that have newer versions available. It parses this JSON output to identify which packages need upgrading.

5. **Package Upgrading**: For each outdated package, the agent runs `npm install package@latest --save` to upgrade to the absolute latest version. It also runs `npm install --legacy-peer-deps` to handle any peer dependency conflicts.

6. **Change Comparison**: The agent compares the before and after states of package.json to determine exactly which packages were upgraded and what version changes occurred.

7. **Git Operations**: The agent creates a new branch with a unique name (format: auto/dependency-update-{timestamp}), commits the changes to package.json and package-lock.json, and pushes the branch to GitHub.

8. **Pull Request Creation**: Finally, the agent creates a pull request via the GitHub API with a descriptive title and body that lists all upgraded packages with their old and new versions.

9. **Memory Recording**: The agent records the upgrade details in memory.json so the frontend can display what packages were upgraded and the results after each cycle.

---

## Project Structure

The project follows a modular architecture with clear separation of concerns:

```
openclaw-guardian/
├── config/
│   └── config_loader.py      # Configuration management and validation
├── utils/
│   └── logger.py             # Logging setup and utilities
├── skills/
│   ├── repo_monitor.py       # Git clone/pull operations
│   ├── dependency_checker.py # npm outdated checker
│   ├── upgrade_executor.py   # npm update/install operations
│   ├── pr_creator.py         # Git branch & PR creation via GitHub API
│   └── memory_manager.py     # Memory storage for upgrade details
├── tests/
│   ├── test_config_loader.py
│   ├── test_dependency_checker.py
│   ├── test_memory_manager.py
│   └── test_integration.py
├── logs/                     # Log files directory
├── main.py                  # Main entry point
├── config.yaml              # Configuration file
├── memory.json              # Memory storage for upgrade details
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

### Component Descriptions

**config/config_loader.py**: Handles loading configuration from config.yaml and environment variables. It supports ${VAR_NAME} syntax for environment variable substitution and validates all required fields.

**utils/logger.py**: Provides logging functionality that writes to both console and file. Supports different log levels (DEBUG, INFO, WARNING, ERROR).

**skills/repo_monitor.py**: Manages Git operations including repository cloning, pulling latest changes, branch checking, and working directory status.

**skills/dependency_checker.py**: Runs `npm outdated` to identify outdated packages and parses the JSON output into a structured format.

**skills/upgrade_executor.py**: Performs the actual package upgrades using npm commands. Handles backup and restore of package.json, validates installations, and compares before/after states.

**skills/pr_creator.py**: Handles all GitHub-related operations including branch creation, committing changes, pushing to remote, and creating pull requests via the GitHub REST API.

**skills/memory_manager.py**: Stores details of upgraded packages in memory.json. This information is used to update the frontend with the results of each cycle, including which packages were upgraded and the pull request URL. The memory is cleared whenever the user saves new configuration or reloads the page.

---

## Installation

### Prerequisites

Before installing OpenClaw Guardian, ensure you have the following:

- Python 3.8 or higher
- Git
- Node.js and npm
- GitHub Personal Access Token with repo permissions

### Step-by-Step Installation

1. **Clone the Repository**

   ```bash
   git clone <repository-url>
   cd openclaw-guardian
   ```

2. **Install Python Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   The required dependencies include:
   - PyYAML for configuration file parsing
   - python-dotenv for .env file support
   - requests for HTTP API calls

3. **Start the Frontend**

   The application comes with a frontend interface. Start the frontend which will:
   - Provide a user interface for entering GitHub credentials
   - Launch the backend agent with your credentials
   
   ```bash
   # Run the frontend (details in Frontend section below)
   ```

**Note:** You do NOT need to create a `.env` file or manually edit `config.yaml`. All credentials (GitHub token and repository URL) are entered through the frontend interface.

---

## Configuration

OpenClaw Guardian is designed with a frontend-backend architecture where the GitHub credentials (token and repository URL) are provided through the frontend interface, not stored in configuration files.

### Important: Do Not Edit config.yaml

**Please do not manually edit the config.yaml file with your GitHub token or repository URL.** The configuration file should remain as-is with placeholder values. The credentials are securely passed to the backend through the frontend when you run the application.

### Configuration File Purpose

The config.yaml is pre-configured with default settings that the system uses:

```yaml
github:
  token: ''  # Will be provided by frontend
  repo_url: ''  # Will be provided by frontend

agent:
  check_interval: 3600  # Check every hour (in seconds)
  branch_prefix: "auto/dependency-update"

paths:
  memory_file: ./memory.json
  working_directory: ./repos
```

### Configuration Options

The following settings are available in config.yaml. You do not need to modify the GitHub settings as they are provided by the frontend:

| Setting | Description | Required | Default |
|---------|-------------|----------|---------|
| github.token | GitHub Personal Access Token | Provided by Frontend | - |
| github.repo_url | GitHub repository URL to monitor | Provided by Frontend | - |
| agent.check_interval | Seconds between dependency checks | No | 3600 |
| agent.branch_prefix | Prefix for PR branch names | No | auto/dependency-update |
| paths.working_directory | Directory for cloned repos | No | ./repos |
| paths.memory_file | Path to memory JSON file | No | ./memory.json |

### How Credentials Are Provided

1. When you access the frontend interface, you will be prompted to enter:
   - Your GitHub Personal Access Token (with repo permissions)
   - The GitHub repository URL you want to monitor

2. These credentials are then securely passed to the backend (OpenClaw Guardian) when you start the agent

3. The backend uses these credentials to perform all GitHub operations (cloning, committing, creating PRs)

---

## Usage

### Running the Agent

**Run Once (for testing):**

```bash
python main.py --once
```

**Run Continuously:**

```bash
python main.py
```

**Run with Verbose Logging:**

```bash
python main.py --verbose
```

**Use Custom Config File:**

```bash
python main.py --config my-config.yaml
```

### Command-Line Options

- `--once`: Run a single cycle and exit (useful for testing)
- `--config`: Specify a custom configuration file path (default: config.yaml)
- `--verbose`: Enable debug-level logging for detailed output

### Example Output

When running successfully, you'll see output similar to:

```
============================================================
  OpenClaw Guardian - Automated Dependency Updater
============================================================

Config file: config.yaml
Run mode: Continuous
Log level: INFO

Initializing OpenClaw Guardian...
Initialization complete!
Starting main loop (check every 3600 seconds)

=== Cycle 1 ===
Step 1: Cloning repository fresh
Cloning https://github.com/user/repo...
npm install completed successfully
Step 2: Checking for outdated packages
Found 3 outdated packages — processing all of them
Step 3: Upgrading dependencies to latest versions
Successfully upgraded 3 packages
Step 4: Creating pull request
Pull request created: https://github.com/user/repo/pull/5
Cycle complete!
Waiting 3600 seconds before next check...
```

---

## Frontend Interface

OpenClaw Guardian comes with a web-based frontend interface that makes it easy to configure and run the agent without manually editing configuration files.

### How the Frontend Works

1. **Access the Frontend**: Launch the frontend application (see project files in `/frontend` directory)

2. **Enter Credentials**: Through the web interface, you will be prompted to enter:
   - **GitHub Personal Access Token**: Your GitHub token with repo permissions
   - **Repository URL**: The GitHub repository you want to monitor (e.g., https://github.com/username/repo)

3. **Start the Agent**: Once you enter your credentials through the frontend, they are securely passed to the backend agent which starts running with your configuration

4. **View Results**: The frontend displays the status and results of each cycle, including:
   - Number of packages upgraded
   - List of upgraded packages with version changes
   - Pull request URLs
   - Historical statistics

### Memory and Session Management

The application uses a session-based approach for memory management:

- **After Each Cycle**: The agent saves the upgraded package details (package names, PR URL, timestamp) to memory.json. This information is displayed on the frontend so you can see exactly what was upgraded.

- **When You Save New Config**: When you enter new GitHub credentials and click "Save Configuration", the application automatically clears:
  - All previously cloned repositories
  - Previous memory (upgrade history)
  - Session statistics

- **When You Reload the Page**: Refreshing or reloading the web page triggers a full reset that clears:
  - All cloned repositories
  - Memory file
  - Configuration credentials
  - Session counters

This ensures a completely fresh start every time you want to run with new credentials.

### Why Use the Frontend?

- **Security**: Your GitHub token is never stored in configuration files
- **Convenience**: Easy to switch between different repositories
- **Visual Feedback**: See the agent's activity in real-time
- **No Manual Configuration**: No need to edit YAML files or environment variables

---

## Technical Details

### Technology Stack

- **Language**: Python 3.8+
- **Package Manager**: pip
- **APIs**: GitHub REST API
- **External Tools**: Git, Node.js, npm
- **Configuration**: YAML

### Dependencies

- **PyYAML**: YAML configuration file parsing
- **python-dotenv**: Environment variable loading from .env files
- **requests**: HTTP library for GitHub API calls

### Data Storage

**memory.json Structure:**

```json
{
    "last_updated": [
        {
            "branch": "auto/dependency-update-1705312200",
            "packages": ["lodash", "axios"],
            "timestamp": "2024-01-15T10:35:00Z",
            "pr_url": "https://github.com/user/repo/pull/5"
        }
    ],
    "successful_upgrades": 8,
    "repo_url": "https://github.com/user/repo"
}
```

The memory.json file stores:
- **last_updated**: List of upgrades performed, each containing branch name, list of packages upgraded, timestamp, and PR URL
- **successful_upgrades**: Total count of successful upgrades
- **repo_url**: The repository URL that was processed

This information is used by the frontend to display the results of each cycle.

### Key Design Decisions

1. **Session-Based Memory**: Each time you save new configuration or reload the page, the memory is cleared. This ensures a completely fresh start with no previous data influencing new runs.

2. **Fresh Cloning**: The repository is always cloned fresh on each cycle. This ensures we're working with the latest code and avoids any local modification issues.

3. **Package-Level Upgrades**: Instead of using `npm update` which only upgrades to semver-satisfying versions, the agent uses `npm install package@latest` to get absolute latest versions.

4. **Branch Per Cycle**: Each cycle creates a new branch with a unique timestamp. This ensures clean, isolated changes that can be reviewed independently.

5. **Cleanup After Cycle**: The cloned repository is deleted after each cycle to prevent disk space issues and ensure clean state for the next cycle.

---

## Architecture

OpenClaw Guardian follows a modular skill-based architecture where each component handles a specific responsibility:

### Main Orchestrator (main.py)

The `OpenClawGuardian` class serves as the main orchestrator that coordinates all components. It manages the lifecycle of each cycle and handles the workflow from start to finish.

### Skill Modules

Each skill module encapsulates a specific capability:

- **RepoMonitor**: Handles all Git operations (clone, pull, branch management)
- **DependencyChecker**: Inspects npm packages for outdated versions
- **UpgradeExecutor**: Performs actual package upgrades
- **PRCreator**: Manages GitHub API interactions for branches and PRs
- **MemoryManager**: Saves upgrade details for frontend display

### Configuration System

The configuration is managed through the frontend interface. When you save your credentials through the frontend, they are written to config.yaml and used by the backend agent.

---

## Workflow

### Complete Cycle Workflow

```
START CYCLE
    │
    ▼
┌─────────────────────┐
│  Clone Repository  │
│  (with auth token)  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Run npm install   │
│  (install deps)     │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Run npm outdated  │
│  (check packages)  │
└─────────────────────┘
    │
    ▼
    ▼ Outdated? ──NO──► NO ACTION ──► UPDATE FRONTEND ──► END
    │
   YES
    │
    ▼
┌─────────────────────┐
│  Upgrade packages   │
│  (npm install @    │
│   latest for each)  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Create Git branch  │
│  (auto/dep-update)  │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Commit changes     │
│  (package.json,    │
│   package-lock)    │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Push to GitHub    │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Create Pull        │
│  Request            │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Save to Memory    │
│  (packages, PR)    │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Update Frontend   │
│  (show results)    │
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  Cleanup repo       │
│  (delete clone)     │
└─────────────────────┘
    │
    ▼
   END
```

---

## API Requirements

### GitHub API

The agent requires a GitHub Personal Access Token with the following permissions:

- **repo**: Full control of private repositories

To create a token:
1. Go to GitHub → Settings → Developer settings
2. Click "Personal access tokens" → "Tokens (classic)"
3. Generate new token with repo scope
4. Enter this token in the frontend interface when prompted

**Note:** You do not need to store this token anywhere. Simply enter it through the frontend when you start the agent.

---

## License

MIT License

---

## Acknowledgments

OpenClaw Guardian was developed for the OpenClaw hackathon. It demonstrates autonomous agent capabilities, multi-step reasoning, tool usage, and persistent state management.
