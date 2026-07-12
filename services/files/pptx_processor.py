"""PPTX: faqat matn o'zgaradi, dizayn/rasm/joylashuv saqlanadi.

Matn har slaydning BARCHA <a:t> tugunlaridan yig'iladi (matn qutilari, jadvallar,
guruhlangan shakllar, ichma-ich) — HECH BIR JOY TASHLANMAYDI.
"""

from pptx import Presentation

from services.files.base import BaseProcessor, FileAnalysis

_A_T = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"


def _collect_text_nodes(prs) -> list:
    nodes = []
    for slide in prs.slides:
        for t in slide._element.iter(_A_T):
            if t.text and t.text.strip():
                nodes.append(t)
    return nodes


class PptxProcessor(BaseProcessor):
    unit_name = "slayd"

    def analyze(self, path: str) -> FileAnalysis:
        prs = Presentation(path)
        slides = len(prs.slides._sldIdLst)
        tokens = max(1, slides)
        return FileAnalysis(unit_count=slides, unit_name=self.unit_name, token_cost=tokens)

    def _extract(self, path: str):
        prs = Presentation(path)
        nodes = _collect_text_nodes(prs)
        segments = [t.text for t in nodes]
        return (prs, nodes), segments

    def _apply(self, context, corrected: list[str], out_path: str) -> None:
        prs, nodes = context
        for node, text in zip(nodes, corrected):
            node.text = text
        prs.save(out_path)
