from typing import NewType
from yaml import safe_load as yaml_load

from utils import pretty_print_timetable

Day = NewType('Day', str)
Slot = NewType('Slot', int)
Room = NewType('Room', str)
Teacher = NewType('Teacher', str)
Course = NewType('Course', str)

type Var = tuple[Day, Slot, Room]
type Val = tuple[Teacher, Course] | None
type Sol = dict[Var, Val]

V_DAY = 0; V_SLOT = 1; V_ROOM = 2
A_TEACHER = 0; A_COURSE = 1

class Commons:
    SLOTS: list[Slot]
    DAYS: list[Day]
    ROOMS: list[Room]
    TEACHERS: list[Teacher]
    COURSES: list[Course]
    REP_ROOMS: dict[Room, set[Course]]
    REP_COURSES: dict[Course, set[Teacher]]
    CAP_ROOMS: dict[Room, int]
    CAP_COURSES: dict[Course, int]
    FREE_DAYS: dict[Teacher, set[Day]] = {}
    FREE_SLOTS: dict[Teacher, set[Slot]] = {}
    TOTAL_SLOTS: int

    TOTAL_CAPACITY: int
    NEEDED_CAPACITY: int

    _input_file: str
    _initialized = False

    @staticmethod
    def read_data(file: str):
        Commons._input_file = file
        with open(file, 'r') as f:
            data = yaml_load(f)
            Commons.SLOTS = list(map(lambda s: Slot(int(s[1:].split(',')[0])), data['Intervale']))
            Commons.DAYS = data['Zile']
            Commons.TOTAL_SLOTS = len(Commons.SLOTS) * len(Commons.DAYS)
            Commons.ROOMS = data['Sali'].keys()
            Commons.TEACHERS = data['Profesori'].keys()
            Commons.COURSES = data['Materii'].keys()
            Commons.REP_ROOMS = {room: set(data['Sali'][room]['Materii']) for room in Commons.ROOMS}
            Commons.REP_COURSES = {course: set() for course in Commons.COURSES}
            for teacher in Commons.TEACHERS:
                for course in data['Profesori'][teacher]['Materii']:
                    Commons.REP_COURSES[course].add(teacher)
            Commons.CAP_ROOMS = {room: data['Sali'][room]['Capacitate'] for room in Commons.ROOMS}
            Commons.CAP_COURSES = {course: data['Materii'][course] for course in Commons.COURSES}
            for teacher in Commons.TEACHERS:
                Commons.FREE_DAYS[teacher] = set()
                Commons.FREE_SLOTS[teacher] = set()
                for pref in data['Profesori'][teacher]['Constrangeri']:
                    if pref[0] != '!': continue 
                    pref = pref[1:]
                    if '-' in pref:
                        [start, end] = pref.split('-')
                        for slot in range(int(start), int(end), 2):
                            Commons.FREE_SLOTS[teacher].add(Slot(slot))
                    else: Commons.FREE_DAYS[teacher].add(pref)
        
        Commons.TOTAL_CAPACITY = len(Commons.DAYS) * len(Commons.SLOTS) * sum(Commons.CAP_ROOMS.values())
        Commons.NEEDED_CAPACITY = sum(Commons.CAP_COURSES.values())
        Commons._initialized = True

    @staticmethod
    def data_ready() -> bool:
        return Commons._initialized
    
    @staticmethod
    def print_timetable(timetable: Sol):
        print(pretty_print_timetable({
            day: {
                (slot, slot + 2): {
                    room: timetable.get((day, slot, room)) for room in Commons.ROOMS
                } for slot in Commons.SLOTS
            } for day in Commons.DAYS
        }, Commons._input_file))