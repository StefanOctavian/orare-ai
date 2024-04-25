""" This module exists firstly because numpy's typing was annoying me and
    secondly to test different implementations for an efficient list allowing
    O(1) insert and remove from front immutably """
from __future__ import annotations
from copy import deepcopy
from typing import Generic, TypeVar, overload

T = TypeVar('T')

class ViewList(Generic[T]):
    _lst : list[T]
    _start : int
    _end : int

    def __init__(self, lst: list[T]):
        self._lst = lst
        self._start = 0
        self._end = len(lst)

    def _cow(self):
        """ Copy-on-write """
        self._lst = self._lst[self._start:self._end]

    @overload
    def __getitem__(self, key: int) -> T: ...
    @overload
    def __getitem__(self, key: slice) -> ViewList[T]: ...

    def __getitem__(self, key: slice | int) -> ViewList[T] | T:
        if isinstance(key, slice):
            new = ViewList(self._lst)
            new._start = self._start + key.start
            new._end = self._start + key.stop if key.stop is not None else self._end
            return new
        return self._lst[self._start + key]
    
    def __setitem__(self, key: int, value: T):
        self._cow()
        self._lst[self._start + key] = value

    def __len__(self) -> int:
        return self._end - self._start
    
    def __iter__(self):
        for i in range(self._start, self._end):
            yield self._lst[i]

    def __repr__(self):
        return f'{self._lst[self._start:self._end]}'
    
    def __str__(self):
        return f'{self._lst[self._start:self._end]}'
    
    def __bool__(self):
        return self._start != self._end
    
    def __copy__(self):
        return ViewList(self._lst[self._start:self._end])
    
    def __deepcopy__(self, memo):
        return ViewList([deepcopy(self._lst[i]) for i in range(self._start, self._end)])
