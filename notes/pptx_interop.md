# PowerPoint Interoperability

## python-pptx -> Microsoft PowerPoint: Fully compatible

python-pptx generates standard Office Open XML (.pptx) files. These open natively in:
- Microsoft PowerPoint (Windows, Mac, Web) — full fidelity
- Google Slides (via import) — most features preserved
- Keynote (via import) — basic features

The .pptx files we generate use only standard shapes, textboxes, connectors, and images.
No macros, no VBA, no custom XML extensions. This means 100% compatibility with MS PowerPoint.

## LibreOffice Impress -> PDF: Good but not identical

LibreOffice is used only for PDF preview generation during development. Known differences:
- Font metrics slightly different (Calibri rendering varies)
- Some rounded rectangle corner radii render differently
- Connector line routing may differ slightly
- Shape shadows/effects may render differently

**For final output: always open .pptx files in Microsoft PowerPoint**, not LibreOffice.
The PDF exports are approximations for quick review only.

## Recommendation

- Use .pptx files directly in Microsoft PowerPoint for all real presentations
- Use LibreOffice PDF export only for quick review during development
- The native PowerPoint shapes (nodes, connectors, text) will look identical in MS PowerPoint
  to how they look in any other PowerPoint file
