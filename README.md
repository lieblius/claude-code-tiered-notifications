# Claude Code Tiered Notifications

Smart notification system for Claude Code that shows immediate macOS notifications and delayed push notifications to your phone.

## How It Works

1. **Immediate**: macOS notification appears right away
2. **Delayed**: If you don't use Claude Code for 30 seconds, sends push notification to your phone
3. **Smart cancellation**: Any Claude Code activity cancels the delayed notification

## Installation

### Prerequisites
```bash
brew install terminal-notifier
```

### Setup
1. Clone this repository
2. `uv sync`
3. Copy `example_config.json` to `~/.claude/notification_config.json` and edit the ntfy topic
4. Add the hooks to your `~/.claude/settings.json` (see `claude_code_hook_config.json`)
5. Install ntfy app on your phone and subscribe to your topic

## Configuration

Edit `~/.claude/notification_config.json`:

```json
{
  "enabled_tiers": ["macos", "ntfy"],
  "delayed_tiers": ["ntfy"],
  "delay_seconds": 30,
  "tier_configs": {
    "macos": {},
    "ntfy": {
      "topic": "your-unique-topic-name",
      "server": "https://ntfy.sh",
      "priority": "default",
      "tags": "computer,claude"
    }
  }
}
```

## Testing

```bash
echo '{"title": "Test", "message": "Hello!"}' | ./tiered_notifier.py
```

