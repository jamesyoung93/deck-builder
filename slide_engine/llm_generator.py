"""LLM-powered deck generation from natural language."""
from __future__ import annotations
import json, yaml
from pathlib import Path
from .schema import Deck, StylePreset, SlideType
from .pptx_builder import PptxBuilder

SYSTEM_PROMPT = """You are a consulting-quality presentation architect. Given a user's request, produce a YAML deck specification. Rules:
1. Every slide title must be a complete sentence stating a takeaway.
2. Use the pyramid principle: lead with the answer.
3. One message per slide.
4. Include source citations where data is referenced.

Available slide types: cover, agenda, section_divider, executive_summary, action_bullets, two_column, three_column, data_callout, bar_chart, framework, timeline, quote, closing
Available styles: executive_dark, corporate_clean, accent_green, neutral

Output ONLY valid YAML starting with "deck:" - no markdown fences, no explanation."""

class DeckGenerator:
    def __init__(self, api_key=None, base_url=None, model="gpt-4o", timeout=120, extra_headers=None):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}

    def generate(self, prompt, output_path="output.pptx", style="neutral", num_slides=None):
        user_msg = prompt
        if num_slides: user_msg += f"\n\nTarget: approximately {num_slides} slides."
        user_msg += f"\n\nUse style: {style}"
        yaml_text = self._call_llm(user_msg)
        deck = self._parse_yaml(yaml_text, style)
        self._maybe_add_flow(deck, output_path)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        PptxBuilder().build(deck, output)
        return str(output)

    def generate_yaml(self, prompt, style="neutral"):
        return self._call_llm(prompt + f"\n\nUse style: {style}")

    def build_from_yaml(self, yaml_text, output_path="output.pptx"):
        deck = self._parse_yaml(yaml_text)
        self._maybe_add_flow(deck, output_path)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        PptxBuilder().build(deck, output)
        return str(output)

    def _call_llm(self, user_message):
        import urllib.request, urllib.error
        url = f"{self.base_url}/chat/completions"
        if "/serving-endpoints/" in self.base_url or "/invocations" in self.base_url:
            url = self.base_url
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        headers.update(self.extra_headers)
        body = {"model": self.model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}], "temperature": 0.3, "max_tokens": 8000}
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"LLM API returned {e.code}: {error_body[:500]}") from e
        if "choices" in data: return data["choices"][0]["message"]["content"]
        elif "output" in data: return data["output"]
        else: raise RuntimeError(f"Unexpected response: {list(data.keys())}")

    def _parse_yaml(self, yaml_text, default_style="neutral"):
        text = yaml_text.strip()
        if text.startswith("```"):
            text = "\n".join(l for l in text.split("\n") if not l.strip().startswith("```"))
        try: data = yaml.safe_load(text)
        except yaml.YAMLError as e: raise ValueError(f"Invalid YAML: {e}\n\n{text[:1000]}")
        if data is None: raise ValueError(f"Empty YAML:\n{text[:500]}")
        if "deck" not in data:
            if "title" in data: data = {"deck": data}
            elif "slides" in data: data = {"deck": {"title": "Untitled", "slides": data["slides"]}}
        deck_data = data.get("deck", data)
        if "style" not in deck_data: deck_data["style"] = default_style
        return Deck.from_dict(data)

    def _maybe_add_flow(self, deck, output_path):
        if any(s.type == SlideType.PROCESS_FLOW for s in deck.slides): return
        try:
            from .flow_integration import insert_auto_flow
            from .styles import get_style
            s = get_style(deck.style.value)
            bg = s.colors.background if s.dark_mode else "#FFFFFF"
            insert_auto_flow(deck, Path(output_path).parent / "flow_diagrams", bg_color=bg)
        except Exception: pass

def generate_deck(prompt, output_path="output.pptx", api_key=None, base_url=None, model="gpt-4o", style="neutral"):
    """One-liner: natural language to .pptx."""
    return DeckGenerator(api_key=api_key, base_url=base_url, model=model).generate(prompt, output_path=output_path, style=style)


def load_yaml_text(yaml_text):
    """
    Robust YAML loader for LLM-generated deck specs.
    Handles all common formats: dict with 'deck' key, bare dict, list of slides,
    markdown fences, extra whitespace, etc.
    
    Usage in Databricks:
        from slide_engine.llm_generator import load_yaml_text
        from slide_engine.pptx_builder import PptxBuilder
        
        deck = load_yaml_text(\"\"\"<paste YAML here>\"\"\")
        PptxBuilder().build(deck, "/dbfs/FileStore/reports/my_deck.pptx")
    """
    import yaml as _yaml
    
    text = yaml_text.strip()
    
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    
    # Strip leading "yaml" if present
    if text.startswith("yaml\n"):
        text = text[5:]
    
    try:
        data = _yaml.safe_load(text)
    except _yaml.YAMLError as e:
        raise ValueError(f"Could not parse YAML: {e}")
    
    if data is None:
        raise ValueError("YAML parsed as empty. Check your input.")
    
    # Handle: list of slides (no deck wrapper)
    if isinstance(data, list):
        data = {"deck": {"title": "Presentation", "style": "neutral", "slides": data}}
    
    # Handle: dict with 'slides' but no 'deck' wrapper
    elif isinstance(data, dict) and "slides" in data and "deck" not in data:
        data = {"deck": data}
    
    # Handle: dict with 'deck' key (correct format)
    elif isinstance(data, dict) and "deck" in data:
        pass
    
    # Handle: dict with 'title' but no 'deck' wrapper
    elif isinstance(data, dict) and "title" in data:
        data = {"deck": data}
    
    # Handle: something else entirely
    elif isinstance(data, dict):
        data = {"deck": data}
    
    else:
        raise ValueError(f"Unexpected YAML structure: {type(data)}")
    
    # Ensure deck has required fields
    deck_data = data.get("deck", {})
    if not isinstance(deck_data, dict):
        raise ValueError(f"'deck' key should be a dictionary, got {type(deck_data)}")
    
    if "title" not in deck_data:
        deck_data["title"] = "Presentation"
    if "style" not in deck_data:
        deck_data["style"] = "neutral"
    if "slides" not in deck_data:
        deck_data["slides"] = []
    
    # Ensure each slide has a 'type'
    for i, slide in enumerate(deck_data.get("slides", [])):
        if isinstance(slide, dict) and "type" not in slide:
            slide["type"] = "action_bullets"
    
    data["deck"] = deck_data
    return Deck.from_dict(data)
