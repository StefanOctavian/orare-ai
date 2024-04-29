from abc import ABC, abstractmethod
from copy import copy
from itertools import tee
from math import inf
import random
from typing import Generator, TypeVar, cast

DEBUG = False
def dlog(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

class HillClimbing[Sol, Action](ABC):
    _best_solution: Sol | None
    _best_cost: float

    _solution: Sol
    _cost: float
    _max_iter: int

    def __init__(self, max_iter: int):
        self._max_iter = max_iter

    @abstractmethod
    def _generate_initial_solution(self) -> Sol:
        pass

    @abstractmethod
    def _evaluate(self, solution: Sol) -> float:
        pass

    @abstractmethod
    def _generate_actions(self) -> Generator[Action, None, None]:
        pass

    @abstractmethod
    def _evaluate_action(self, action: Action) -> float:
        """ Returns the delta of the cost function if the action is applied. """
        pass

    @abstractmethod
    def _apply_action(self, action: Action) -> None:
        pass

    @abstractmethod
    def _restart(self) -> None:
        pass

    def _reset(self) -> None:
        self._best_solution = None
        self._best_cost = inf

    def solve(self) -> Sol:
        self._reset()
        for _ in range(self._max_iter):
            self._restart()
            self._solution = self._generate_initial_solution()
            self._cost = self._evaluate(self._solution)
            dlog(f"Initial cost: {self._cost}")
            while True:
                actions, actions_copy = tee(self._generate_actions())
                better_actions = ((a, delta) for a in actions if (delta := self._evaluate_action(a)) < 0)
                action, delta = next(better_actions, (None, 0))
                if not action:
                    dlog("No better actions")
                    if self._cost < self._best_cost:
                        dlog("New best cost found")
                        self._best_cost = self._cost
                        self._best_solution = copy(self._solution)

                    if self._best_cost != 0 and random.random() > 0.5:
                        dlog("Allowing worse action")
                        action = next(actions_copy, None)
                        if action is None:
                            break
                        delta = self._evaluate_action(action)
                    else: 
                        break
                self._apply_action(action)
                self._cost += delta
                dlog(f"{delta=} new cost={self._cost}")
                if self._cost == 0:
                    self._best_solution = copy(self._solution)
                    self._best_cost = 0
                    break

            if self._best_cost == 0:
                break

        self._best_solution = cast(Sol, self._best_solution)
        return self._best_solution