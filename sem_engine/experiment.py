"""
Experiment tracking and versioning system.

Maintains a ledger of all experiments, versions, and results.
Tracks what works and what fails so future iterations can learn.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExperimentEntry:
    """A single experiment run."""
    version_id: str
    timestamp: str
    input_case: str
    toolchain: str
    layout_strategy: str
    schema_version: str
    design_choices: list[str]
    score: float
    failures: list[str]
    improvements: list[str]
    verdict: str             # keep / reject / refine / explore
    reuse_pattern: bool
    notes: str = ""
    source_path: str = ""
    output_path: str = ""

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "timestamp": self.timestamp,
            "input_case": self.input_case,
            "toolchain": self.toolchain,
            "layout_strategy": self.layout_strategy,
            "schema_version": self.schema_version,
            "design_choices": self.design_choices,
            "score": self.score,
            "failures": self.failures,
            "improvements": self.improvements,
            "verdict": self.verdict,
            "reuse_pattern": self.reuse_pattern,
            "notes": self.notes,
            "source_path": self.source_path,
            "output_path": self.output_path,
        }


class ExperimentTracker:
    """Manages experiment logging, versioning, and pattern tracking."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.experiments_dir = self.base_dir / "experiments"
        self.artifacts_dir = self.base_dir / "artifacts"
        self.patterns_dir = self.base_dir / "patterns"
        self.ledger_path = self.experiments_dir / "ledger.json"
        self.changelog_path = self.base_dir / "CHANGELOG.md"

        # Ensure directories exist
        for d in [self.experiments_dir, self.artifacts_dir,
                  self.patterns_dir / "good", self.patterns_dir / "bad"]:
            d.mkdir(parents=True, exist_ok=True)

        self._version_counter = self._load_counter()

    def _load_counter(self) -> int:
        if self.ledger_path.exists():
            try:
                ledger = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                return len(ledger.get("entries", []))
            except Exception:
                pass
        return 0

    def _next_version(self) -> str:
        self._version_counter += 1
        return f"v{self._version_counter:03d}"

    def log_experiment(self, entry: ExperimentEntry) -> str:
        """Log an experiment and return the version id."""
        if not entry.version_id:
            entry.version_id = self._next_version()
        if not entry.timestamp:
            entry.timestamp = datetime.now(timezone.utc).isoformat()

        # Load or create ledger
        ledger = {"entries": []}
        if self.ledger_path.exists():
            try:
                ledger = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        ledger["entries"].append(entry.to_dict())
        self.ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

        # Version the artifacts
        version_dir = self.artifacts_dir / entry.version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        if entry.source_path and Path(entry.source_path).exists():
            shutil.copy2(entry.source_path, version_dir)
        if entry.output_path and Path(entry.output_path).exists():
            shutil.copy2(entry.output_path, version_dir)

        # Save entry metadata
        meta_path = version_dir / "metadata.json"
        meta_path.write_text(json.dumps(entry.to_dict(), indent=2), encoding="utf-8")

        return entry.version_id

    def save_pattern(self, name: str, category: str, content: dict, reason: str):
        """Save a known-good or known-bad pattern."""
        pattern_dir = self.patterns_dir / category
        pattern_dir.mkdir(parents=True, exist_ok=True)

        pattern = {
            "name": name,
            "category": category,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": content,
        }
        path = pattern_dir / f"{name}.json"
        path.write_text(json.dumps(pattern, indent=2), encoding="utf-8")

    def get_ledger(self) -> list[dict]:
        """Get all experiment entries."""
        if self.ledger_path.exists():
            try:
                ledger = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                return ledger.get("entries", [])
            except Exception:
                pass
        return []

    def get_leaderboard(self) -> list[dict]:
        """Get experiments sorted by score (highest first)."""
        entries = self.get_ledger()
        return sorted(entries, key=lambda e: e.get("score", 0), reverse=True)

    def get_best_for_case(self, case_name: str) -> dict | None:
        """Get the best-scoring experiment for a specific case."""
        entries = [e for e in self.get_ledger() if e.get("input_case") == case_name]
        if not entries:
            return None
        return max(entries, key=lambda e: e.get("score", 0))

    def get_toolchain_stats(self) -> dict[str, dict]:
        """Get aggregate stats by toolchain."""
        stats: dict[str, dict] = {}
        for entry in self.get_ledger():
            tc = entry.get("toolchain", "unknown")
            if tc not in stats:
                stats[tc] = {"count": 0, "total_score": 0, "failures": 0, "keeps": 0}
            stats[tc]["count"] += 1
            stats[tc]["total_score"] += entry.get("score", 0)
            if entry.get("verdict") == "reject":
                stats[tc]["failures"] += 1
            elif entry.get("verdict") == "keep":
                stats[tc]["keeps"] += 1

        for tc, s in stats.items():
            s["avg_score"] = round(s["total_score"] / max(1, s["count"]), 2)

        return stats

    def update_changelog(self, version_id: str, message: str):
        """Append an entry to the changelog."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"\n## [{version_id}] - {timestamp}\n{message}\n"

        if self.changelog_path.exists():
            current = self.changelog_path.read_text(encoding="utf-8")
        else:
            current = "# Changelog\n\nAll notable changes to the SEM Builder framework.\n"

        self.changelog_path.write_text(current + entry, encoding="utf-8")

    def save_best(self, case_name: str, source_path: Path, output_path: Path | None):
        """Copy best artifacts to the best/ directory."""
        best_dir = self.artifacts_dir / "best" / case_name
        best_dir.mkdir(parents=True, exist_ok=True)

        if source_path.exists():
            shutil.copy2(source_path, best_dir)
        if output_path and output_path.exists():
            shutil.copy2(output_path, best_dir)
