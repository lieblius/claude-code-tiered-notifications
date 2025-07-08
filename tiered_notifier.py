#!/usr/bin/env python3
"""
Tiered Notifications for Claude Code
A extensible notification system that supports multiple notification tiers.
"""

import json
import sys
import subprocess
import os
import requests
import time
import tempfile
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NotificationConfig:
    """Configuration for notification preferences"""

    enabled_tiers: list[str]
    default_tier: str = "macos"
    tier_configs: Dict[str, Dict[str, Any]] = None
    delayed_tiers: list[str] = None
    delay_seconds: int = 30

    def __post_init__(self):
        if self.tier_configs is None:
            self.tier_configs = {}
        if self.delayed_tiers is None:
            self.delayed_tiers = ["ntfy"]


class NotificationTier(ABC):
    """Abstract base class for notification tiers"""

    @abstractmethod
    def send_notification(self, title: str, message: str, **kwargs) -> bool:
        """Send a notification. Returns True if successful."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this notification tier is available on the system."""
        pass


class MacOSNotificationTier(NotificationTier):
    """macOS notification using terminal-notifier with Claude Code icon"""

    def send_notification(self, title: str, message: str, **kwargs) -> bool:
        try:
            # Use terminal-notifier with Claude app bundle identifier for proper icon
            cmd = [
                "terminal-notifier",
                "-title",
                title,
                "-message",
                message,
                "-sender",
                "com.anthropic.claudefordesktop",
            ]

            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            # Fallback to osascript if terminal-notifier fails
            try:
                script = f'''
                display notification "{message}" with title "{title}"
                '''
                subprocess.run(
                    ["osascript", "-e", script], check=True, capture_output=True
                )
                return True
            except subprocess.CalledProcessError:
                return False

    def is_available(self) -> bool:
        try:
            subprocess.run(["osascript", "-e", ""], check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False


class NtfyNotificationTier(NotificationTier):
    """Push notification using ntfy.sh"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.topic = self.config.get("topic", "claude-code-notifications")
        self.server = self.config.get("server", "https://ntfy.sh")
        self.priority = self.config.get("priority", "default")
        self.tags = self.config.get("tags", "claude")

    def send_notification(self, title: str, message: str, **kwargs) -> bool:
        try:
            url = f"{self.server}/{self.topic}"
            headers = {"Title": title, "Priority": self.priority, "Tags": self.tags}

            response = requests.post(
                url, data=message.encode("utf-8"), headers=headers, timeout=10
            )

            return response.status_code == 200
        except requests.RequestException:
            return False

    def is_available(self) -> bool:
        try:
            # Test if we can reach the ntfy server
            response = requests.get(f"{self.server}", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False


class SessionTracker:
    """Track Claude Code session activity for delayed notifications"""

    def __init__(self):
        self.activity_file = Path.home() / ".claude" / "session_activity.json"
        self.activity_file.parent.mkdir(exist_ok=True)

    def mark_activity(self, session_id: str):
        """Mark that session is active (PreToolUse detected)"""
        try:
            activity_data = {}
            if self.activity_file.exists():
                with open(self.activity_file, "r") as f:
                    activity_data = json.load(f)

            activity_data[session_id] = time.time()

            with open(self.activity_file, "w") as f:
                json.dump(activity_data, f)
        except Exception:
            pass  # Fail silently if we can't track

    def is_session_idle(self, session_id: str, idle_threshold: int) -> bool:
        """Check if session has been idle for longer than threshold"""
        try:
            if not self.activity_file.exists():
                return True

            with open(self.activity_file, "r") as f:
                activity_data = json.load(f)

            last_activity = activity_data.get(session_id)
            if last_activity is None:
                return True

            return (time.time() - last_activity) > idle_threshold
        except Exception:
            return True  # If we can't determine, assume idle


class TieredNotifier:
    """Main notification system that manages multiple notification tiers"""

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)

        # Initialize tiers with their configurations
        self.config.tier_configs.get("macos", {})
        ntfy_config = self.config.tier_configs.get("ntfy", {})

        self.tiers: Dict[str, NotificationTier] = {
            "macos": MacOSNotificationTier(),
            "ntfy": NtfyNotificationTier(ntfy_config),
        }

    def _load_config(self, config_path: Optional[str] = None) -> NotificationConfig:
        """Load notification configuration from file or use defaults"""
        if config_path is None:
            config_path = os.path.expanduser("~/.claude/notification_config.json")

        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config_data = json.load(f)
                    return NotificationConfig(**config_data)
        except (json.JSONDecodeError, TypeError):
            pass

        # Default configuration
        return NotificationConfig(enabled_tiers=["macos", "ntfy"], default_tier="macos")

    def register_tier(self, name: str, tier: NotificationTier):
        """Register a new notification tier"""
        self.tiers[name] = tier

    def send_notification(
        self, title: str, message: str, tier: Optional[str] = None
    ) -> bool:
        """Send notification using specified tier or default"""
        if tier is None:
            tier = self.config.default_tier

        if tier not in self.tiers:
            print(f"Warning: Notification tier '{tier}' not found", file=sys.stderr)
            return False

        if tier not in self.config.enabled_tiers:
            print(f"Warning: Notification tier '{tier}' is disabled", file=sys.stderr)
            return False

        notification_tier = self.tiers[tier]

        if not notification_tier.is_available():
            print(
                f"Warning: Notification tier '{tier}' is not available", file=sys.stderr
            )
            return False

        return notification_tier.send_notification(title, message)

    def send_tiered_notification(
        self, title: str, message: str, session_id: Optional[str] = None
    ) -> bool:
        """Send immediate notifications and schedule delayed ones"""
        success = False

        # Send immediate tiers (not in delayed_tiers)
        immediate_tiers = [
            t for t in self.config.enabled_tiers if t not in self.config.delayed_tiers
        ]
        for tier_name in immediate_tiers:
            if tier_name in self.tiers:
                tier = self.tiers[tier_name]
                if tier.is_available():
                    if tier.send_notification(title, message):
                        success = True

        # Schedule delayed tiers if session_id provided
        if session_id and self.config.delayed_tiers:
            self._schedule_delayed_notifications(title, message, session_id)

        if not success:
            print("Warning: No immediate notification tiers available", file=sys.stderr)

        return success

    def _schedule_delayed_notifications(
        self, title: str, message: str, session_id: str
    ):
        """Schedule delayed notifications that fire if session stays idle"""

        # Create a separate script to handle the delay
        delay_script = f"""#!/usr/bin/env python3
import time
import json
import requests
from pathlib import Path

# Wait for the delay
time.sleep({self.config.delay_seconds})

# Check if session is still idle
activity_file = Path.home() / ".claude" / "session_activity.json"
is_idle = True

try:
    if activity_file.exists():
        with open(activity_file, 'r') as f:
            activity_data = json.load(f)
        
        last_activity = activity_data.get("{session_id}")
        if last_activity is not None:
            is_idle = (time.time() - last_activity) > {self.config.delay_seconds}
except:
    pass

# Send delayed notification if still idle
if is_idle:
    try:
        for tier_config in {json.dumps([(name, self.config.tier_configs.get(name, {})) for name in self.config.delayed_tiers])}:
            tier_name, config = tier_config
            if tier_name == "ntfy":
                topic = config.get("topic", "claude-code-notifications")
                server = config.get("server", "https://ntfy.sh")
                priority = config.get("priority", "default")
                tags = config.get("tags", "claude")
                
                url = f"{{server}}/{{topic}}"
                headers = {{
                    "Title": "{title}",
                    "Priority": priority,
                    "Tags": tags
                }}
                
                requests.post(url, data="{message}".encode('utf-8'), headers=headers, timeout=10)
    except:
        pass
"""

        # Write and execute the delay script
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(delay_script)
            delay_script_path = f.name

        # Make it executable and run in background
        os.chmod(delay_script_path, 0o755)
        subprocess.Popen(
            [delay_script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def main():
    """Main entry point for the notification script"""
    try:
        # Read input from stdin (Claude Code hook data)
        input_data = json.load(sys.stdin)

        # Check if this is an activity tracking hook (PreToolUse, PostToolUse, Stop)
        if "tool_name" in input_data or "stop_hook_active" in input_data:
            # This is an activity hook, track activity
            session_id = input_data.get("session_id")
            if session_id:
                tracker = SessionTracker()
                tracker.mark_activity(session_id)
            sys.exit(0)  # Don't send notifications for activity hooks

        # This is a Notification hook
        title = input_data.get("title", "Claude Code")
        message = input_data.get("message", "Notification")
        session_id = input_data.get("session_id")

        # Initialize notifier
        notifier = TieredNotifier()

        # Send notification with session tracking
        success = notifier.send_tiered_notification(title, message, session_id)

        if success:
            print(f"Notification sent: {title} - {message}")
            sys.exit(0)
        else:
            print("Failed to send notification", file=sys.stderr)
            sys.exit(1)

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
