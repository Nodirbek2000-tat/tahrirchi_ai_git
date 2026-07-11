from pptx import Presentation

from services.files.base import BaseProcessor, FileAnalysis


def _iter_runs(shape):
    runs = []
    if shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                if run.text and run.text.strip():
                    runs.append(run)
    if shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                for para in cell.text_frame.paragraphs:
                    for run in para.runs:
                        if run.text and run.text.strip():
                            runs.append(run)
    if shape.shape_type == 6:  # GROUP
        for sub in shape.shapes:
            runs.extend(_iter_runs(sub))
    return runs


class PptxProcessor(BaseProcessor):
    unit_name = "slayd"

    def _collect_runs(self, prs):
        runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                runs.extend(_iter_runs(shape))
        return runs

    def analyze(self, path: str) -> FileAnalysis:
        prs = Presentation(path)
        slides = len(prs.slides._sldIdLst)
        tokens = max(1, slides)
        return FileAnalysis(unit_count=slides, unit_name=self.unit_name, token_cost=tokens)

    def _extract(self, path: str):
        prs = Presentation(path)
        runs = self._collect_runs(prs)
        segments = [run.text for run in runs]
        return (prs, runs), segments

    def _apply(self, context, corrected: list[str], out_path: str) -> None:
        prs, runs = context
        for run, text in zip(runs, corrected):
            run.text = text
        prs.save(out_path)
