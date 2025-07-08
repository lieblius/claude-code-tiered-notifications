# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a tiered notification system for Claude Code hooks that provides immediate macOS notifications and delayed push notifications to mobile devices. The system uses intelligent activity detection to cancel delayed notifications when the user is actively working with Claude Code.

## Core Architecture

The system is built around an extensible notification tier architecture:

- **NotificationTier (ABC)**: Abstract base class defining the interface for notification methods
- **MacOSNotificationTier**: Sends immediate macOS notifications using `terminal-notifier` with Claude Code icon
- **NtfyNotificationTier**: Sends push notifications via ntfy.sh service
- **TieredNotifier**: Main orchestrator that manages multiple tiers and handles delayed notifications
- **SessionTracker**: Tracks Claude Code activity to determine when to cancel delayed notifications

## Key Components

### tiered_notifier.py + tiered_notifier_wrapper.py
Main application (`tiered_notifier.py`) with portable wrapper:
- **tiered_notifier.py**: Core logic that detects hook types, manages notifications, tracks activity
- **tiered_notifier_wrapper.py**: Ensures script runs with correct uv environment regardless of current directory
- Detects hook type (PreToolUse/PostToolUse/Stop vs Notification) from stdin JSON
- For activity hooks: updates session activity tracker and exits
- For notification hooks: sends immediate notifications and schedules delayed ones
- Uses background processes (not threads) for delayed notifications to survive main process exit

### Configuration System
- `~/.claude/notification_config.json`: User notification preferences
- `enabled_tiers`: Which notification methods to use
- `delayed_tiers`: Which tiers should be delayed vs immediate
- `delay_seconds`: How long to wait before sending delayed notifications
- `tier_configs`: Per-tier configuration (ntfy topic, server, etc.)

### Activity Detection
The system tracks Claude Code activity through multiple hook events:
- **PreToolUse**: When Claude Code is about to use a tool
- **PostToolUse**: When Claude Code finishes using a tool  
- **Stop**: When Claude Code finishes responding
- **Notification**: When Claude Code sends a notification (triggers the notification system)

Activity is tracked in `~/.claude/session_activity.json` with session IDs and timestamps.

## Development Commands

```bash
# Set up development environment
uv sync

# Test the notification system
echo '{"title": "Test", "message": "Hello!"}' | ./tiered_notifier_wrapper.py

# Test specific notification tier
echo '{"title": "Test", "message": "Hello!", "session_id": "test-123"}' | ./tiered_notifier_wrapper.py

# Test activity tracking (should not send notification)
echo '{"tool_name": "Read", "session_id": "test-123"}' | ./tiered_notifier_wrapper.py
```

## Important Implementation Details

### Delayed Notification Mechanism
Delayed notifications use temporary Python scripts executed as separate processes rather than daemon threads, ensuring they survive after the main hook process exits. The delayed script:
1. Sleeps for the configured delay period
2. Checks if the session is still idle by reading the activity tracker
3. Sends the delayed notification only if no activity detected

### Claude Code Icon Integration
macOS notifications use `terminal-notifier` with `-sender "com.anthropic.claudefordesktop"` to display the Claude Code application icon instead of Terminal or Script Editor icons.

### Hook Configuration
The system requires multiple Claude Code hooks to work properly:
- **Activity hooks** (PreToolUse, PostToolUse, Stop): Track when user is active
- **Notification hook**: Trigger the notification system
- All hooks point to the same `tiered_notifier.py` script which determines behavior based on input JSON structure

### Configuration Loading
Falls back gracefully if configuration files don't exist, using sensible defaults. Configuration is loaded from `~/.claude/notification_config.json` and merged with defaults defined in the `NotificationConfig` dataclass.