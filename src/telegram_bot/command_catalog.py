"""Shared Telegram command registry used by /start and /help."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSpec:
    name: str
    syntax: str
    summary: str
    example: str
    visible_in_start: bool = True
    visible_in_help: bool = True

    @property
    def start_line(self) -> str:
        return f"{self.syntax} - {self.summary}"


COMMAND_CATALOG: tuple[CommandSpec, ...] = (
    CommandSpec(
        name="brief",
        syntax="/brief [1-8|refresh]",
        summary="Fetch the latest brief, limit the number of stories, or force a refresh.",
        example="/brief 3",
    ),
    CommandSpec(
        name="story",
        syntax="/story <n>",
        summary="Show the source links and fuller context for story n from the latest brief.",
        example="/story 1",
    ),
    CommandSpec(
        name="lastbrief",
        syntax="/lastbrief",
        summary="Re-open the most recent brief without regenerating it.",
        example="/lastbrief",
    ),
    CommandSpec(
        name="write",
        syntax="/write <n|x_url|https_url|text>",
        summary="Turn a brief item, X post, article URL, or pasted text into Hebrew draft variants.",
        example="/write https://x.com/user/status/123",
    ),
    CommandSpec(
        name="save",
        syntax="/save <variant_index>",
        summary="Save one variant from your last /write session as a draft in the queue.",
        example="/save 1",
    ),
    CommandSpec(
        name="queue",
        syntax="/queue",
        summary="Show queue counts and the newest review-ready draft IDs.",
        example="/queue",
    ),
    CommandSpec(
        name="draft",
        syntax="/draft <id>",
        summary="Show the status, preview, and studio link for a saved draft.",
        example="/draft 42",
    ),
    CommandSpec(
        name="approve",
        syntax="/approve <id>",
        summary="Mark a saved draft as approved for the publishing workflow.",
        example="/approve 42",
    ),
    CommandSpec(
        name="status",
        syntax="/status",
        summary="Show quick counts for drafts, scheduled, and published content.",
        example="/status",
    ),
    CommandSpec(
        name="schedule",
        syntax="/schedule",
        summary="Show the configured brief and alert automation times.",
        example="/schedule",
    ),
    CommandSpec(
        name="health",
        syntax="/health",
        summary="Check API and database health.",
        example="/health",
    ),
    CommandSpec(
        name="help",
        syntax="/help",
        summary="Show examples and supported input formats.",
        example="/help",
    ),
)


def visible_start_commands() -> list[CommandSpec]:
    return [item for item in COMMAND_CATALOG if item.visible_in_start]


def visible_help_commands() -> list[CommandSpec]:
    return [item for item in COMMAND_CATALOG if item.visible_in_help]


def render_start_text() -> str:
    lines = ["HFI Content Studio Bot is online.", "", "Commands:"]
    lines.extend(item.start_line for item in visible_start_commands())
    return "\n".join(lines)


def render_help_text() -> str:
    lines = ["HFI Bot Help", "", "Examples:"]
    for item in visible_help_commands():
        lines.append(f"{item.syntax}")
        lines.append(f"- {item.summary}")
        lines.append(f"- Example: {item.example}")
        lines.append("")
    return "\n".join(lines).strip()

