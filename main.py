from math import inf
from typing import Literal, cast
from sys import argv, exit
from csp import PCSP, Constraint
from efficient_lists import ViewList
from utils import pretty_print_timetable
from yaml import safe_load as yaml_load

SLOTS: list[int]
DAYS: list[str]
ROOMS: list[str]
TEACHERS: list[str]
COURSES: list[str]
REP_ROOMS: dict[str, list[str]]
REP_COURSES: dict[str, list[str]]
CAP_ROOMS: dict[str, int]
CAP_COURSES: dict[str, int]
PREFERENCES: dict[str, set[range | str]] = {}

TOTAL_CAPACITY: int
NEEDED_CAPACITY: int

def read_data(file: str):
    global SLOTS
    global DAYS
    global ROOMS
    global TEACHERS
    global COURSES
    global REP_ROOMS
    global REP_COURSES
    global CAP_ROOMS
    global CAP_COURSES
    global TOTAL_CAPACITY
    global NEEDED_CAPACITY
    global PREFERENCES

    with open(file, 'r') as f:
        data = yaml_load(f)
        SLOTS = list(map(lambda s: int(s[1:].split(',')[0]), data['Intervale']))
        DAYS = data['Zile']
        ROOMS = data['Sali'].keys()
        TEACHERS = data['Profesori'].keys()
        COURSES = data['Materii'].keys()
        REP_ROOMS = {room: data['Sali'][room]['Materii'] for room in ROOMS}
        REP_COURSES = {course: [] for course in COURSES}
        for teacher in TEACHERS:
            for course in data['Profesori'][teacher]['Materii']:
                REP_COURSES[course].append(teacher)
        CAP_ROOMS = {room: data['Sali'][room]['Capacitate'] for room in ROOMS}
        CAP_COURSES = {course: data['Materii'][course] for course in COURSES}
        for teacher in TEACHERS:
            PREFERENCES[teacher] = set()
            for pref in data['Profesori'][teacher]['Constrangeri']:
                if pref[0] != '!': continue 
                pref = pref[1:]
                if '-' in pref:
                    [start, end] = pref.split('-')
                    pref = range(int(start), int(end), 2)
                PREFERENCES[teacher].add(pref)
    
    TOTAL_CAPACITY = len(DAYS) * len(SLOTS) * sum(CAP_ROOMS.values())
    NEEDED_CAPACITY = sum(CAP_COURSES.values())

type VarType = tuple[str, int, str] # day, slot, room
type Domain = tuple[str, str] | None # teacher, course
V_DAY = 0; V_SLOT = 1; V_ROOM = 2
A_TEACHER = 0; A_COURSE = 1
def sort(a: list, f): 
    a.sort(key=f)
    return a

def csp():
    pcsp = PCSP[VarType, Domain]()
    variables = [(day, slot, room) for day in DAYS 
                for slot in SLOTS for room in ROOMS]

    # order teachers ascending by preference for a slot
    def teacher_order(var: VarType, a: tuple[str, str]):
        teacher, _ = a
        day, slot, _ = var
        pref = PREFERENCES[teacher]
        return 2 * (day in pref) + ((slot, slot + 2) in pref)

    domains = {
        var: ViewList(sort([
            (teacher, course) for course in REP_ROOMS[var[V_ROOM]]
                              for teacher in REP_COURSES[course]
        ], lambda a: teacher_order(var, a)) + [None])
        for var in variables
    }

    constraints: list[Constraint[VarType, Domain]] = []
    for teacher, pref_set in PREFERENCES.items():
        for pref in pref_set:
            pref_range = isinstance(pref, range)
            check = lambda teacher_: lambda val: not val or val[A_TEACHER] != teacher_
            constraints += [
                ([(day, slot, room)], check(teacher), 1)
                for day in (DAYS if pref_range else [pref])
                for slot in (SLOTS if not pref_range else cast(range, pref))
                for room in ROOMS
            ]

    # variables that are dependent on the value of variables above
    # (day, slot, teacher) -> (room, course): all None by default
    # teacher -> number of slots the teacher teaches: 0
    # course -> occupied room capacity: 0
    # (used room capacity, used effective capacity): (0, 0)
    USED_CAP_VAR = 'U'
    U_ROOM_CAP = 0
    U_EFFECTIVE_CAP = 1
    dep_vars = {
        teacher: 0 for teacher in TEACHERS }|{
        course: 0 for course in COURSES }|{
        USED_CAP_VAR: (0, 0)
    }
    pcsp.dependent_vars = dep_vars

    # assignment of a variable to a value can trigger changes in dependent variables
    def dependencies(var: VarType, val: Domain):
        """ returns a list of tuples (affected_dependent_var, update_function, update_cost)
            update_function is old_val -> (new_val, success) 
            a failed update will increase the cost of the current assignment """
        day, slot, room = var
        teacher, course = val or (None, None)
        need_cap = CAP_COURSES[course] - cast(int, dep_vars[course]) if course else 0
        eff_used_cap = min(CAP_ROOMS[room], need_cap)
        restrictions = [
            # a teacher can only teach one course at a time in one room
            ((day, slot, teacher), lambda old_val: ((room, course), not old_val), inf),
            # a teacher can not teach more than 7 slots a week
            (teacher, lambda old_val: ((old_val or 0) + 1, (old_val or 0) < 7), inf),
            # the capacity of a course is not exceedingly allocated - speed up the search
            (course, lambda old_val: (old_val + CAP_ROOMS[room], 
                old_val < CAP_COURSES[course]), inf)
        ] if course else []
        restrictions.append(
            # the capacity of a course is occupied by the number of slots it is taught
            (USED_CAP_VAR, lambda old_val: ((
                room_cap := old_val[U_ROOM_CAP] + CAP_ROOMS[room],
                eff_cap  := old_val[U_EFFECTIVE_CAP] + eff_used_cap 
            ), TOTAL_CAPACITY - room_cap >= NEEDED_CAPACITY - eff_cap), inf)
        )
        return restrictions

    # total capacity over all rooms and all slots (T)
    # total needed capacity for all courses (Y)
    # total occupied capacity for all courses (C)
    # total effective used capacity for all courses (Z)
    # constraint: T - C >= Y - Z

    pcsp.dependencies = dependencies
    return pcsp.solve(ViewList(variables), domains, constraints, acceptable_cost=1)

def hc():
    pass

def main(algo: Literal['csp'] | Literal['hc'], input_file: str):
    if algo == 'csp': 
        read_data(f'inputs/{input_file}.yaml')
        solution, cost, iterations = csp()
        print(pretty_print_timetable({
            day: {
                (slot, slot + 2): {
                    room: solution.get((day, slot, room)) for room in ROOMS
                } for slot in SLOTS
            } for day in DAYS
        }, f"inputs/{input_file}.yaml"))
        print(f"Final cost: {cost}, iterations: {iterations}")
    else: hc()

if __name__ == '__main__':
    if len(argv) != 3:
        print('Usage: python3 main.py [csp|hc] input_file')
        exit(1)
    assert argv[1] in ['csp', 'hc'], 'Invalid argument'
    argv[1] = cast(Literal['csp'] | Literal['hc'], argv[1])
    main(argv[1], argv[2])