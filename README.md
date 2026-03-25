# deck-builder

Generate consulting-quality PowerPoint presentations from natural language. All slides are native PowerPoint shapes — independently movable and editable.

---

## Step 1: Install

```python
# Cell 1: Install dependencies (once per cluster)
%pip install python-pptx pyyaml matplotlib fontawesome pillow

# Cell 2: Install deck-builder
%pip install --no-deps https://github.com/jamesyoung93/deck-builder/raw/master/deck_builder-0.2.0-py3-none-any.whl

# Cell 3: Restart Python (required after install)
dbutils.library.restartPython()
```

If the wheel URL is blocked, download `deck_builder-0.2.0-py3-none-any.whl` from the [repo](https://github.com/jamesyoung93/deck-builder) and upload it:

```python
%pip install python-pptx pyyaml matplotlib fontawesome pillow
%pip install --no-deps /dbfs/FileStore/deck_builder-0.2.0-py3-none-any.whl
# or: /Volumes/your_catalog/your_schema/your_volume/deck_builder-0.2.0-py3-none-any.whl
# or: /Workspace/Users/you@company.com/deck_builder-0.2.0-py3-none-any.whl
dbutils.library.restartPython()
```

---

## Step 2: Import

```python
from slide_engine.llm_generator import DeckGenerator
```

---

## Step 3: Connect your LLM endpoint

### Databricks Foundation Model API (recommended)

```python
DATABRICKS_HOST = spark.conf.get("spark.databricks.workspaceUrl")
DATABRICKS_TOKEN = dbutils.secrets.get("my-scope", "my-token")

gen = DeckGenerator(
    api_key=DATABRICKS_TOKEN,
    base_url=f"https://{DATABRICKS_HOST}/serving-endpoints/databricks-meta-llama-3-1-70b-instruct/invocations",
    model="databricks-meta-llama-3-1-70b-instruct",
)
```

### Databricks External Model (OpenAI/Anthropic via gateway)

```python
gen = DeckGenerator(
    api_key=dbutils.secrets.get("my-scope", "my-token"),
    base_url=f"https://{DATABRICKS_HOST}/serving-endpoints/my-openai-endpoint/invocations",
    model="gpt-4o",
)
```

### OpenAI direct

```python
gen = DeckGenerator(
    api_key=dbutils.secrets.get("my-scope", "openai-key"),
    model="gpt-4o",
)
```

### Anthropic direct

```python
gen = DeckGenerator(
    api_key=dbutils.secrets.get("my-scope", "anthropic-key"),
    base_url="https://api.anthropic.com/v1",
    model="claude-sonnet-4-20250514",
)
```

### Azure OpenAI

```python
gen = DeckGenerator(
    api_key=dbutils.secrets.get("my-scope", "azure-key"),
    base_url="https://your-resource.openai.azure.com/openai/deployments/gpt-4o",
    model="gpt-4o",
    extra_headers={"api-version": "2024-02-15-preview"},
)
```

---

## Step 4: Generate a deck

```python
gen.generate(
    "Build a 10-slide board presentation. Revenue was $42M, up 18% YoY. "
    "EBITDA margin 28%. APAC grew fastest at 31%. We need board approval "
    "for a $15M expansion into Southeast Asia.",
    output_path="/dbfs/FileStore/reports/board_q2.pptx",
    style="executive_dark",
)
```

Available styles: `executive_dark` | `corporate_clean` | `accent_green` | `neutral`

---

## Step 5: Download

```python
displayHTML('<a href="/files/reports/board_q2.pptx">Download board_q2.pptx</a>')
```

Also browsable at: Databricks UI → Catalog → DBFS → FileStore → reports

Other save locations:

```python
# Unity Catalog Volume
gen.generate("...", output_path="/Volumes/catalog/schema/volume/my_deck.pptx")

# Workspace Files
gen.generate("...", output_path="/Workspace/Users/you@company.com/my_deck.pptx")
```

---

## Full copy-paste example

```python
# Cell 1: Install (once per cluster)
%pip install python-pptx pyyaml matplotlib fontawesome pillow
%pip install --no-deps https://github.com/jamesyoung93/deck-builder/raw/master/deck_builder-0.2.0-py3-none-any.whl
dbutils.library.restartPython()
```

```python
# Cell 2: Setup
from slide_engine.llm_generator import DeckGenerator

DATABRICKS_HOST = spark.conf.get("spark.databricks.workspaceUrl")
DATABRICKS_TOKEN = dbutils.secrets.get("my-scope", "my-token")

gen = DeckGenerator(
    api_key=DATABRICKS_TOKEN,
    base_url=f"https://{DATABRICKS_HOST}/serving-endpoints/databricks-meta-llama-3-1-70b-instruct/invocations",
    model="databricks-meta-llama-3-1-70b-instruct",
)
```

```python
# Cell 3: Generate
gen.generate(
    "Quarterly business review. Revenue $42M (+18%), margin 28%, "
    "APAC strongest region. Requesting $15M for expansion.",
    output_path="/dbfs/FileStore/reports/qbr.pptx",
    style="executive_dark",
)
```

```python
# Cell 4: Download
displayHTML('<a href="/files/reports/qbr.pptx">Download QBR deck</a>')
```

---

## Advanced: review YAML before building

```python
# Generate YAML spec without building
yaml_text = gen.generate_yaml("Product launch plan for enterprise SaaS")
print(yaml_text)  # Review and edit if needed

# Build from edited YAML
gen.build_from_yaml(yaml_text, "/dbfs/FileStore/reports/launch_plan.pptx")
```


---

## Using any LLM to generate decks (manual workflow)

If your Databricks environment does not support direct API calls, use any LLM (Claude, ChatGPT, Databricks AI Playground) with this master prompt.

### Step 1: Paste this system prompt into your LLM

```
You are a PowerPoint deck architect. When I describe a presentation, produce a YAML specification that I will paste into my deck-builder tool.

Rules:
1. Every slide title must be a complete sentence stating a takeaway -- not a topic label.
2. Lead with the answer (pyramid principle).
3. One message per slide.
4. Include source citations where data is referenced.

Available slide types and their fields:

- cover: title, subtitle, body
- agenda: title, agenda_items (list of strings)
- section_divider: title
- executive_summary: title, bullets (list of {lead, detail}), source
- action_bullets: title, subtitle, bullets (list of {lead, detail}), source
- two_column: title, columns (list of {heading, bullets}), source
- three_column: title, columns (list of {heading, bullets}), source
- data_callout: title, callouts (list of {value, label, context}), source
- bar_chart: title, bars (list of {label, value, highlight, annotation}), source
- framework: title, cells (list of {label, description, row, col}), x_axis, y_axis, source
- timeline: title, phases (list of {label, duration, items}), source
- quote: title, quote_text, quote_attribution
- closing: title, subtitle, bullets (list of {lead, detail})

Available styles: executive_dark, corporate_clean, accent_green, neutral

Output ONLY valid YAML starting with "deck:" -- no markdown fences, no explanation, no commentary. Just the YAML.
```

### Step 2: Describe what you want

> Make a 12-slide board presentation. Revenue was $42M (+18% YoY), EBITDA margin 28%, APAC grew 31%. We need approval for $15M Southeast Asia expansion. Use executive_dark style.

### Step 3: Copy the YAML output and paste into Databricks

```python
from slide_engine.schema import Deck
from slide_engine.pptx_builder import PptxBuilder
import yaml

yaml_text = """
<paste the YAML from your LLM here>
"""

deck = Deck.from_dict(yaml.safe_load(yaml_text))
PptxBuilder().build(deck, "/dbfs/FileStore/reports/my_deck.pptx")
displayHTML("<a href='/files/reports/my_deck.pptx'>Download my_deck.pptx</a>")
```


---

## Without LLM (direct Python API)

```python
from slide_engine.schema import Deck, Slide, SlideType, StylePreset, BulletPoint, DataCallout
from slide_engine.pptx_builder import PptxBuilder

deck = Deck(title="Q2 Review", style=StylePreset.EXECUTIVE_DARK)
deck.add_slide(Slide(type=SlideType.COVER, title="Q2 Review", subtitle="June 2026"))
deck.add_slide(Slide(
    type=SlideType.DATA_CALLOUT,
    title="Three metrics show strong momentum heading into H2",
    callouts=[
        DataCallout("$42M", "Revenue", "+18% YoY"),
        DataCallout("28%", "EBITDA Margin", "+200bps vs plan"),
        DataCallout("92", "NPS", "Up from 78"),
    ],
))
deck.add_slide(Slide(type=SlideType.CLOSING, title="Thank you"))
PptxBuilder().build(deck, "/dbfs/FileStore/reports/q2.pptx")
```

---

## Slide types

| Type | Use |
|------|-----|
| `cover` | Title slide |
| `agenda` | Numbered section list |
| `section_divider` | Section transition |
| `executive_summary` | Key findings with bold lead-ins |
| `action_bullets` | Argument with supporting points |
| `two_column` | Side-by-side comparison |
| `three_column` | Three parallel points |
| `data_callout` | Big numbers in cards |
| `bar_chart` | Horizontal bars |
| `process_flow` | Auto-generated workflow diagram |
| `framework` | 2x2 matrix |
| `timeline` | Phased roadmap |
| `quote` | Emphasis quote |
| `closing` | Thank you / next steps |

## License

MIT
