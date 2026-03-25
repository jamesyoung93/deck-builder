"""
Generator module.

Translates process descriptions into candidate structured representations.
Generates multiple diagram candidates across different backends and strategies.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import ProcessModel, ViewMode
from .renderers import get_renderer, list_renderers, RENDERERS
from .renderers.base import RenderResult, BaseRenderer
from .discriminator import Discriminator, CandidateArtifact, ComparisonReport
from .experiment import ExperimentTracker, ExperimentEntry


class Generator:
    """
    Generates diagram candidates from ProcessModel instances.

    Supports multiple rendering backends and layout strategies.
    Works with the Discriminator to evaluate and rank outputs.
    """

    def __init__(self, output_dir: Path, tracker: ExperimentTracker | None = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tracker = tracker
        self.discriminator = Discriminator()

    def get_available_renderers(self) -> list[str]:
        """Get list of renderers that are actually available."""
        available = []
        for name, cls in RENDERERS.items():
            try:
                r = cls()
                if r.check_available():
                    available.append(name)
            except Exception:
                pass
        return available

    def generate_single(self, model: ProcessModel, renderer_name: str,
                       base_name: str = "diagram",
                       layout_strategy: str = "default") -> CandidateArtifact:
        """Generate and evaluate a single candidate."""
        renderer = get_renderer(renderer_name)
        case_dir = self.output_dir / renderer_name / base_name
        case_dir.mkdir(parents=True, exist_ok=True)

        result = renderer.render(model, case_dir, base_name)
        candidate = self.discriminator.evaluate(model, result)

        # Log experiment if tracker available
        if self.tracker and candidate.score:
            entry = ExperimentEntry(
                version_id="",
                timestamp="",
                input_case=base_name,
                toolchain=renderer_name,
                layout_strategy=layout_strategy,
                schema_version=model.version,
                design_choices=[f"view_mode={model.view_mode.value}"],
                score=candidate.score.total,
                failures=candidate.score.defects,
                improvements=candidate.score.recommendations,
                verdict=candidate.verdict,
                reuse_pattern=candidate.verdict == "keep",
                source_path=str(result.source_path) if result.source_path else "",
                output_path=str(result.output_path) if result.output_path else "",
            )
            self.tracker.log_experiment(entry)

        return candidate

    def generate_all_renderers(self, model: ProcessModel,
                               base_name: str = "diagram") -> ComparisonReport:
        """Generate candidates across all available renderers and compare."""
        candidates = []

        for renderer_name in self.get_available_renderers():
            try:
                candidate = self.generate_single(model, renderer_name, base_name)
                candidates.append(candidate)
            except Exception as e:
                # Create a failed candidate
                result = RenderResult(
                    success=False,
                    renderer_name=renderer_name,
                    errors=[str(e)],
                )
                candidate = self.discriminator.evaluate(model, result)
                candidates.append(candidate)

        report = self.discriminator.compare(base_name, candidates)
        return report

    def generate_multi_view(self, model: ProcessModel,
                           base_name: str = "diagram") -> dict[str, ComparisonReport]:
        """Generate candidates in multiple view modes."""
        reports = {}
        original_mode = model.view_mode

        for view_mode in [ViewMode.PROCESS_FLOW, ViewMode.CAUSAL, ViewMode.MODULAR]:
            model.view_mode = view_mode
            report = self.generate_all_renderers(model, f"{base_name}_{view_mode.value}")
            reports[view_mode.value] = report

        model.view_mode = original_mode
        return reports

    def run_benchmark(self, cases: dict[str, ProcessModel]) -> dict[str, ComparisonReport]:
        """Run all benchmark cases through all renderers."""
        results = {}
        for case_name, model in cases.items():
            report = self.generate_all_renderers(model, case_name)
            results[case_name] = report

            # Save best result
            if self.tracker and report.best_candidate:
                rc = report.best_candidate.render_result
                if rc.source_path and rc.output_path:
                    self.tracker.save_best(case_name, rc.source_path, rc.output_path)

        return results
