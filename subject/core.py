"""Core subject logic."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SubjectState:
    value: int
    history: List[Dict[str, int]]


class Subject:
    def __init__(self, initial_value: int = 0, history: Optional[List[Dict[str, int]]] = None) -> None:
        if history is None:
            history = []
        self.state = SubjectState(value=initial_value, history=list(history))

    def step(self, input_value: int) -> SubjectState:
        new_value = self.state.value + input_value
        event = {"type": "STEP", "input": input_value, "result": new_value}
        new_history = self.state.history + [event]
        self.state = SubjectState(value=new_value, history=new_history)
        return self.state
