"""RAGAs evaluation models for tracking retrieval quality."""

from datetime import datetime, timezone
from statistics import mean

from pydantic import BaseModel, Field, computed_field


class EvalResult(BaseModel):
    question: str
    answer: str
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overall_score(self) -> float:
        return mean([
            self.faithfulness,
            self.answer_relevancy,
            self.context_precision,
            self.context_recall,
        ])


class EvalSuite(BaseModel):
    results: list[EvalResult]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mean_faithfulness(self) -> float:
        return mean(r.faithfulness for r in self.results)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mean_relevancy(self) -> float:
        return mean(r.answer_relevancy for r in self.results)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mean_precision(self) -> float:
        return mean(r.context_precision for r in self.results)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mean_recall(self) -> float:
        return mean(r.context_recall for r in self.results)
