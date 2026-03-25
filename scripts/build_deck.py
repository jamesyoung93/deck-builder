#!/usr/bin/env python3
"""Build a PowerPoint deck from a YAML specification."""

import sys, argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Build consulting-quality PowerPoint decks")
    parser.add_argument("input", help="Deck spec file (YAML)")
    parser.add_argument("-s", "--style", help="Style preset: executive_dark, corporate_clean, accent_green, neutral")
    parser.add_argument("-o", "--output", help="Output .pptx path")
    parser.add_argument("--score", action="store_true", help="Show quality score")
    parser.add_argument("--no-flow", action="store_true", help="Skip auto flow diagram")
    args = parser.parse_args()

    # Add parent to path for non-installed usage
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from slide_engine.schema import Deck, SlideType, StylePreset
    from slide_engine.pptx_builder import PptxBuilder
    from slide_engine.styles import get_style

    spec = Path(args.input)
    if not spec.exists():
        print(f"Error: {spec} not found"); sys.exit(1)

    deck = Deck.load(spec)
    if args.style:
        deck.style = StylePreset(args.style)

    output = Path(args.output) if args.output else Path("output") / f"{spec.stem}.pptx"
    output.parent.mkdir(parents=True, exist_ok=True)

    if not args.no_flow and not any(s.type == SlideType.PROCESS_FLOW for s in deck.slides):
        try:
            from slide_engine.flow_integration import insert_auto_flow
            s = get_style(deck.style.value)
            bg = s.colors.background if s.dark_mode else "#FFFFFF"
            if insert_auto_flow(deck, output.parent / "flow_diagrams", bg_color=bg):
                print("  Auto-generated process flow diagram")
        except Exception:
            pass

    PptxBuilder().build(deck, output)
    print(f"Built: {output} ({output.stat().st_size // 1024} KB)")

    if args.score:
        from slide_engine.critic import DeckCritic
        print(f"\n{DeckCritic().score(deck).summary()}")

if __name__ == "__main__":
    main()
