import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.schemas.criteria import CriteriaResult
from app.services.agents.criteria_extractor import _parse_json


def test_parse_json_with_fences():
    raw = '```json\n{"criteria":[{"category":"Financial","requirement":"Turnover of Rs 5 crore","source_page":3}]}\n```'
    result = CriteriaResult(**_parse_json(raw))
    assert result.criteria[0].category.value == "financial"


def test_unknown_category_falls_back():
    r = CriteriaResult(criteria=[{"category": "weird", "requirement": "Must have GST"}])
    assert r.criteria[0].category.value == "other"


if __name__ == "__main__":
    test_parse_json_with_fences()
    test_unknown_category_falls_back()
    print("All criteria tests passed successfully!")
