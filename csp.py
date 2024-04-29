from __future__ import annotations
from copy import deepcopy
from math import inf
from typing import Any, Callable, Generic, List, Literal, NewType, Sequence, TypeVar, override
from efficient_lists import ViewList

# type variable for the type of a variable (read this 2, 3 times :)))
VarType = TypeVar('VarType')
# type variable for the domain of a variable
Domain = TypeVar('Domain')

type UnaryPredicate[Domain] = Callable[[Domain], bool]
type BinaryPredicate[Domain] = Callable[[Domain, Domain], bool]
type TernaryPredicate[Domain] = Callable[[Domain, Domain, Domain], bool]
type Predicate[Domain] = UnaryPredicate[Domain] | BinaryPredicate[Domain] | TernaryPredicate[Domain]

# we will represent a constraint as ⟨t, r, c⟩ where:
# - t ⊆ VarType: the variables involved in the constraint as a list
# - r : Domainᶜᵃʳᵈ⁽ᵗ⁾ ⟶ bool: the relation that must hold between the variables
# (here, the cartesian product is taken in the order of the variables in t as a list)
# - c: int: the cost of the constraint
type Constraint[VarType, Domain] = tuple[list[VarType], Predicate[Domain], int]
C_VAR_LIST = 0
C_RELATION = 1
C_COST = 2

DEBUG = False
def log(*args, **kwargs):
    if DEBUG: print(*args, **kwargs)

class PCSP(Generic[VarType, Domain]):
    type Solution = dict[VarType, Domain]
    type Dependency = tuple[Any, Callable[[Any | None], tuple[Any, bool]], float]
    # we will implement an optimized version of constraint propagation for the case
    # where setting a variable to a value fully determines the value of another variable
    # based on the assigned value of the first variable and the old value of the second variable
    # and the update of the dependent variable can also fail resulting in an unsatisfied constraint

    _best_solution: Solution
    _solution: Solution
    _best_cost: float  # we will use inf for +∞ which is a float
    _iterations: int

    _domains: dict[VarType, ViewList[Domain]]
    _acceptable_cost: float
    _constraints: dict[VarType, list[Constraint[VarType, Domain]]]

    dependencies: Callable[[VarType, Domain], list[Dependency]]
    dependent_vars: dict[Any, Any] = {}

    def __init__(self):
        self._reset()

    def _reset(self):
        self._solution = {}
        self._best_solution = {}
        self._best_cost = inf
        self._iterations = 0

    def _constraints_for_var(self, var: VarType):
        return (c for c in self._constraints[var] if
                all(v in self._solution for v in c[C_VAR_LIST]))
    
    def _check_constraint(self, constraint: Constraint):
        return constraint[C_RELATION](*[self._solution[var] for var in constraint[C_VAR_LIST]])
    
    def _update_deps(self, var: VarType, val: Domain):
        log(f"\t[dependencies] {var} -> {val}")
        dep_cost = 0
        dep_updates: list[tuple[VarType, Any | None]] = []
        dependecies = self.dependencies(var, val)
        if dependecies is None: return (0, lambda: None)
        for dep_var, update, update_cost in dependecies:
            old_dep_val = self.dependent_vars.get(dep_var)
            new_dep_val, success = update(old_dep_val)
            self.dependent_vars[dep_var] = new_dep_val
            dep_updates.append((dep_var, old_dep_val))
            if not success:
                log(f"\tfailed update for {dep_var}, cost: {update_cost}")
                dep_cost += update_cost
                continue

        def revert():
            for dep_var, old_dep_val in dep_updates:
                if old_dep_val is not None: self.dependent_vars[dep_var] = old_dep_val
                else: del self.dependent_vars[dep_var]

        return dep_cost, revert

    def _PCSP(self, variables: ViewList[VarType], cost: float):
        if cost == inf:
            # if cost is infinite, we did not satisfy a mandatory constraint
            log(f"[exit] infinite cost")
            return False

        if not variables:
            # We reached a new best solution
            log(f"new best solution, {self._solution} cost: {cost}")
            self._best_solution = self._solution
            self._best_cost = cost
            if cost <= self._acceptable_cost:
                log(f"[exit] new best solution is acceptable, exit true")
                return True
            else:
                log(f"[exit] new best solution is not acceptable, exit false")
                return False
        elif cost == self._best_cost:
            # current solution is not better than the best known solution
            log(f"[exit] cost is equal to best cost, exit false")
            return False
            
        for val in self._domains[variables[0]]:
            # try values for the current variable
            if self._PSCP_val(variables, val, cost):
                return True
            elif cost == self._best_cost:
                return False
        
        # no more values to try for the current variable
        return False
        
    def _PSCP_val(self, variables: ViewList[VarType], val: Domain, cost: float):
        # get the current variable and first available value for it
        var = variables[0]
        self._iterations += 1
        log(f"Trying {var} -> {val}")

        # to avoid copying the solution, I will apply an update/revert strategy
        old_val = self._solution.get(var)
        self._solution[var] = val

        # check if the current value satisfies the dependencies
        log(self.dependent_vars)
        dep_cost, revert_dep = self._update_deps(var, val)
        new_cost = cost
        log(f"dependent cost: {dep_cost}")

        if dep_cost < inf:
            evaluable_constraints = self._constraints_for_var(var)
            # log(f"|evaluable_constraints|: {len(list(evaluable_constraints))}")
            new_cost += sum(map(lambda c: c[C_COST], 
                                filter(lambda c: not self._check_constraint(c), 
                                        evaluable_constraints)))
            log(f"evaluated constraints with cost: {new_cost - cost}")

        new_cost += dep_cost
        log(f"added dependent cost, new cost: {new_cost}")

        if new_cost < self._best_cost and new_cost <= self._acceptable_cost:
            log(f"new best acceptable cost. Trying next variable")
            if self._PCSP(variables[1:], new_cost):
                log(f"[exit] partial solution found, exit true")
                return True
        log(f"Trying next value for {var}")
        # revert the solution and dependent variables
        if old_val is not None: self._solution[var] = old_val
        else: del self._solution[var]
        revert_dep()
        
    def solve(self, variables: ViewList[VarType], domains: dict[VarType, ViewList[Domain]], 
              constraints: list[Constraint[VarType, Domain]], acceptable_cost: float):
        self._reset()
        self._domains = deepcopy(domains)
        self._acceptable_cost = acceptable_cost
        self._constraints = {var: [c for c in constraints if var in c[C_VAR_LIST]] for var in variables}
        self._PCSP(variables, 0)
        return self._best_solution, self._best_cost, self._iterations
