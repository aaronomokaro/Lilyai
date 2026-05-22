import json
import os
from typing import List, Optional

from pydantic import BaseModel


class TestCase(BaseModel):
    id: str
    question: str
    expected_answer: str
    expected_citations: List[dict]
    query_type: str
    document_source: str
    capability: str
    is_no_answer: bool = False
    notes: Optional[str] = None


class GroundTruthDataset:
    def __init__(self):
        self.test_cases: List[TestCase] = []
        self._load_dataset()

    def _load_dataset(self):
        dataset_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "data",
            "ground_truth.json",
        )

        if os.path.exists(dataset_path):
            with open(dataset_path, "r") as f:
                data = json.load(f)
                self.test_cases = [TestCase(**case) for case in data]

    def get_by_capability(self, capability: str) -> List[TestCase]:
        return [tc for tc in self.test_cases if tc.capability == capability]

    def get_by_query_type(self, query_type: str) -> List[TestCase]:
        return [tc for tc in self.test_cases if tc.query_type == query_type]

    def get_no_answer_cases(self) -> List[TestCase]:
        return [tc for tc in self.test_cases if tc.is_no_answer]

    def get_sample(self, n: int) -> List[TestCase]:
        import random

        return random.sample(self.test_cases, min(n, len(self.test_cases)))

    def count(self) -> int:
        return len(self.test_cases)


dataset = GroundTruthDataset()
