"""Core subject logic."""

from dataclasses import dataclass
from typing import Dict, List, Optional


STEP_COST = 1


@dataclass
class SubjectState:
    value: int
    history: List[Dict[str, object]]
    budget: int


class Subject:
    def __init__(
        self,
        initial_value: int = 0,
        history: Optional[List[Dict[str, object]]] = None,
        initial_budget: int = 10,
    ) -> None:
        if history is None:
            history = []
        self.state = SubjectState(
            value=initial_value,
            history=list(history),
            budget=initial_budget,
        )

    def step(self, input_value: int) -> SubjectState:
        if self.state.budget < STEP_COST:
            event = {
                "type": "DENY",
                "reason": "NO_BUDGET",
                "input": input_value,
                "budget": self.state.budget,
            }
            new_history = self.state.history + [event]
            self.state = SubjectState(
                value=self.state.value,
                history=new_history,
                budget=self.state.budget,
            )
            return self.state

        new_value = self.state.value + input_value
        new_budget = self.state.budget - STEP_COST
        event = {
            "type": "STEP",
            "input": input_value,
            "result": new_value,
            "cost": STEP_COST,
            "budget_after": new_budget,
        }
        new_history = self.state.history + [event]
        self.state = SubjectState(value=new_value, history=new_history, budget=new_budget)
        return self.state
