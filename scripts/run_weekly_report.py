from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analytics import analyze_dataset, load_input_folder


def main() -> None:
    input_dir = PROJECT_ROOT / "data" / "input"
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_input_folder(input_dir)
    result = analyze_dataset(dataset)
    output_path = reports_dir / "weekly_output_2026-04-01_2026-04-26.md"
    output_path.write_text(result["report_markdown"], encoding="utf-8")
    print(output_path)
    print(result["data_sources"])


if __name__ == "__main__":
    main()
