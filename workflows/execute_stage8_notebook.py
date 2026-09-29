"""Execute Stage 8 audit cells in-process and save display-rich notebook outputs.

This avoids a network-bound Jupyter kernel and works in restricted/offline research
environments. It executes the same code cells, in order, and stores stdout plus PNG
figures as standard nbformat stream/display_data outputs.
"""

from __future__ import annotations

import base64
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg

from topoastero.portability import write_json_lf
from topoastero.style import topoastero_style

ROOT = Path(__file__).parents[1]
NOTEBOOK = ROOT / "notebooks/08_cylindrical_echelle.ipynb"


def main() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    namespace: dict[str, object] = {"__name__": "__notebook__"}
    current = Path.cwd()
    try:
        os.chdir(ROOT)
        for count, cell in enumerate((item for item in notebook["cells"] if item["cell_type"] == "code"), start=1):
            stream = io.StringIO()
            previous_figures = set(plt.get_fignums())
            with topoastero_style(), redirect_stdout(stream):
                exec("".join(cell["source"]), namespace)
            outputs: list[dict[str, object]] = []
            if stream.getvalue():
                outputs.append({"output_type": "stream", "name": "stdout", "text": stream.getvalue().splitlines(keepends=True)})
            for number in set(plt.get_fignums()) - previous_figures:
                figure = plt.figure(number)
                buffer = io.BytesIO()
                FigureCanvasAgg(figure).print_png(buffer)
                encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
                outputs.append({"output_type": "display_data", "data": {"image/png": encoded}, "metadata": {}})
                plt.close(figure)
            cell["outputs"] = outputs
            cell["execution_count"] = count
    finally:
        os.chdir(current)
    write_json_lf(NOTEBOOK, notebook)
    print(f"Stage 8 notebook executed {count} cells in-process")


if __name__ == "__main__":
    main()
