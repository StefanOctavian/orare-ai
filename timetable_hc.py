from itertools import chain, product, zip_longest
from random import choice
import random
from typing import Generator, Iterator, Literal
from commons import A_COURSE, A_TEACHER, Commons, Sol, Var, Val, Room, Teacher, Course, Slot, Day
from hc import HillClimbing

type Action = tuple[Literal['change'], Var, Val] | tuple[Literal['swap'], Var, Var]

DEBUG = False
class TimetableHC(HillClimbing[Sol, Action]):
    _ROOM_ALLOC_WEIGHT: int
    _TEACHER_MAX_HOURS_WEIGHT: int
    _TEACHER_PREF_DAY_WEIGHT: int
    _TEACHER_PREF_SLOT_WEIGHT: int

    _teacher_table: dict[tuple[Day, Slot, Teacher], tuple[Room, Course] | None] = {}
    _teacher_hours: dict[Teacher, int]
    _course_allocs: dict[Course, int]

    def __init__(self):
        if not Commons.data_ready():
            raise Exception("Commons not initialized")
        self._ALL_SLOTS = list(product(Commons.DAYS, Commons.SLOTS, Commons.ROOMS))
        self._ALL_VALUES = lambda room: [(teacher, course) for course in Commons.REP_ROOMS[room]
                                        for teacher in Commons.REP_COURSES[course]]
        self._TEACHER_PREF_SLOT_WEIGHT = 25 # 1
        self._TEACHER_PREF_DAY_WEIGHT = 50 # 2
        self._TEACHER_MAX_HOURS_WEIGHT = 75 # 3 * Commons.TOTAL_SLOTS + 1
        self._ROOM_ALLOC_WEIGHT = 100 # 4 * Commons.TOTAL_SLOTS
        super().__init__(max_iter=1000)

    def _restart(self) -> None:
        self._teacher_table.clear()
        self._teacher_hours = {teacher: 0 for teacher in Commons.TEACHERS}
        self._course_allocs = {course: 0 for course in Commons.COURSES}

    def _generate_initial_solution(self) -> Sol:
        sol = {}
        for (day, slot, room) in self._ALL_SLOTS:
            found = False
            while not found:
                if random.random() < 0.3:
                    course, teacher = None, None
                else:
                    course = choice(list(Commons.REP_ROOMS[room]))
                    teacher = choice(list(Commons.REP_COURSES[course]))
                found = not (teacher and self._teacher_table.get((day, slot, teacher)))

            sol[(day, slot, room)] = (teacher, course) if teacher else None
            if teacher and course:
                self._teacher_table[(day, slot, teacher)] = (room, course)
                self._teacher_hours[teacher] += 1
                self._course_allocs[course] += Commons.CAP_ROOMS[room]
        return sol

    def _evaluate(self, solution: Sol) -> float:
        teacher_max_hours: dict[Teacher, int] = {}
        teacher_pref_day_cost: int = 0
        teacher_pref_slot_cost: int = 0

        for (day, slot, room) in self._ALL_SLOTS:
            val = solution[(day, slot, room)]
            if not val: continue
            teacher, _ = val
            teacher_pref_day_cost += (day in Commons.FREE_DAYS[teacher])
            teacher_pref_slot_cost += (slot in Commons.FREE_SLOTS[teacher])
            teacher_max_hours[teacher] = teacher_max_hours.get(teacher, 0) + 1

        room_alloc_cost = sum(max(0, Commons.CAP_COURSES[course] - self._course_allocs[course]) 
                              for course in self._course_allocs)
        teacher_max_hours_cost = sum(max(0, teacher_max_hours[teacher] - 7) 
                                     for teacher in teacher_max_hours)
        
        cost = self._ROOM_ALLOC_WEIGHT * room_alloc_cost + \
            self._TEACHER_MAX_HOURS_WEIGHT * teacher_max_hours_cost + \
            self._TEACHER_PREF_DAY_WEIGHT * teacher_pref_day_cost + \
            self._TEACHER_PREF_SLOT_WEIGHT * teacher_pref_slot_cost
        
        if DEBUG:
            print("[Initial Delta report]")
            print(f"\troom alloc: {room_alloc_cost} (w={self._ROOM_ALLOC_WEIGHT})")
            print(f"\tteacher max hours: {teacher_max_hours_cost} (w={self._TEACHER_MAX_HOURS_WEIGHT})")
            print(f"\tteacher pref day: {teacher_pref_day_cost} (w={self._TEACHER_PREF_DAY_WEIGHT})")
            print(f"\tteacher pref slot: {teacher_pref_slot_cost} (w={self._TEACHER_PREF_SLOT_WEIGHT})")
            print("[/]")
            Commons.print_timetable(solution)
        return cost

    def _generate_actions(self):
        random.shuffle(self._ALL_SLOTS)
        changes: Iterator[Action] = (
            ('change', (day, slot, room), val)
            for (day, slot, room) in self._ALL_SLOTS
            for val in chain(self._ALL_VALUES(room), [None])
            if not (val and self._teacher_table.get((day, slot, val[A_TEACHER])))
            and (val or random.random() < 0.3)
        )
        p = lambda x: True
        a = lambda i, t: t if not t else t 
        swaps: Iterator[Action] = (
            ('swap', (day1, slot1, room1), (day2, slot2, room2))
            for (day1, slot1, room1), (day2, slot2, room2) in product(self._ALL_SLOTS, repeat=2)
            if p(((day1, slot1, room1), (day2, slot2, room2))) and
               a(1, (val1 := self._solution.get((day1, slot1, room1)) or (None, None))) and
               a(2, (val2 := self._solution.get((day2, slot2, room2)) or (None, None))) and
               a(3, ((course1 := val1[A_COURSE]) or True) and ((course2 := val2[A_COURSE]) or True)) and
               a(4, ((teacher1 := val1[A_TEACHER]) or True) and ((teacher2 := val2[A_TEACHER]) or True)) and
               a(5, ((day1, slot1, room1) != (day2, slot2, room2))) and
               a(6, (not course2 or course2 in Commons.REP_ROOMS[room1])) and
               a(7, (not course1 or course1 in Commons.REP_ROOMS[room2])) and
               a(8, not (teacher2 and self._teacher_table.get((day1, slot1, teacher2)))) and
               a(9, not (teacher1 and self._teacher_table.get((day2, slot2, teacher1))))
        )
        return (x for x in chain.from_iterable(zip_longest(changes, swaps)) if x is not None)
    
    def _evaluate_action(self, action: Action, debug=False) -> float:
        if action[0] == 'change':
            return self._evaluate_change_action(action[1], action[2], debug)
        return self._evaluate_swap_action(action[1], action[2], debug)

    # can you believe this whole function runs in O(1) time? (considering teacher's preferences as constant)
    def _evaluate_change_action(self, var: Var, val: Val, debug=False) -> float:
        # the way of choosing actions guarantees that the teacher is not already assigned to the slot
        delta = 0
        day, slot, room = var
        old_teacher, old_course = self._solution[var] or (None, None)
        teacher, course = val or (None, None)
        # check number of hours for the teacher
        delta_hours = (not not teacher and (self._teacher_hours[teacher] >= 7)) - \
                      (not not old_teacher and (self._teacher_hours[old_teacher] > 7))
        delta += self._TEACHER_MAX_HOURS_WEIGHT * delta_hours
        # check if the course is fully allocated
        delta_course = lambda course_, dec: 0 if not course_ else \
            max(0, Commons.CAP_COURSES[course_] - self._course_allocs[course_] - dec * Commons.CAP_ROOMS[room]) - \
            max(0, Commons.CAP_COURSES[course_] - self._course_allocs[course_])
        delta_courses = delta_course(course, 1) + delta_course(old_course, -1)
        delta += self._ROOM_ALLOC_WEIGHT * delta_courses
        # check teacher preferences
        delta_pref_day = (not not teacher and day in Commons.FREE_DAYS[teacher]) - \
                         (not not old_teacher and day in Commons.FREE_DAYS[old_teacher])
        delta += self._TEACHER_PREF_DAY_WEIGHT * delta_pref_day
        delta_pref_slot = (not not teacher and slot in Commons.FREE_SLOTS[teacher]) - \
                          (not not old_teacher and slot in Commons.FREE_SLOTS[old_teacher])
        delta += self._TEACHER_PREF_SLOT_WEIGHT * delta_pref_slot
        if debug:
            tally = sum(max(0, Commons.CAP_COURSES[course] - self._course_allocs[course]) for course in self._course_allocs)
            print(f"[Delta report {var} -> {val}]")
            print(f"\troom alloc: {delta_courses} (w={self._ROOM_ALLOC_WEIGHT})\t(tally: {tally})")
            print(f"\tteacher max hours: {delta_hours} (w={self._TEACHER_MAX_HOURS_WEIGHT})")
            print(f"\tteacher pref day: {delta_pref_day} (w={self._TEACHER_PREF_DAY_WEIGHT})")
            print(f"\tteacher pref slot: {delta_pref_slot} (w={self._TEACHER_PREF_SLOT_WEIGHT})")
            print(f"Total delta: {delta}")
            print("[/]")
        return delta

    def _evaluate_swap_action(self, var1: Var, var2: Var, debug=False) -> float:
        # calculate the delta of the swap by simulating the swap and calculating the sum
        # of the deltas of the changes
        aux_val1 = self._solution[var1]
        change1 = self._evaluate_change_action(var1, self._solution[var2], debug)
        self._apply_action(('change', var1, self._solution[var2]), sim=True)
        change2 = self._evaluate_change_action(var2, aux_val1, debug)
        self._apply_action(('change', var1, aux_val1), sim=True)
        return change1 + change2
    
    def _apply_action(self, action: Action, sim=False) -> None:
        if DEBUG and not sim:
            self._evaluate_action(action, debug=True)
            print(f"Applying action: {action}")
        if action[0] == 'change':
            var, val = action[1], action[2]
            day, slot, room = var
            teacher, course = val or (None, None)
            old_teacher, old_course = self._solution[var] or (None, None)
            self._solution[var] = val
            if teacher and course:
                self._teacher_table[(day, slot, teacher)] = (room, course)
                self._teacher_hours[teacher] += 1
                self._course_allocs[course] += Commons.CAP_ROOMS[room]
            if old_teacher and old_course:
                self._teacher_table[(day, slot, old_teacher)] = None
                self._teacher_hours[old_teacher] -= 1
                self._course_allocs[old_course] -= Commons.CAP_ROOMS[room]
        else:
            val1, val2 = self._solution[action[1]], self._solution[action[2]]
            self._apply_action(('change', action[1], val2), sim=True)
            self._apply_action(('change', action[2], val1), sim=True)
        if DEBUG and not sim:
            Commons.print_timetable(self._solution)