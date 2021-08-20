from dataclasses import dataclass

from typing import Optional, Callable



@dataclass
class MenuItem:
    title: str
    fn: Optional[Callable[..., None]]
    data: Optional[dict] = None

    def on_enter(self):
        if not self.data:
            data = dict()
        else:
            data = self.data
        if self.fn:
            self.fn(**data)


class Menu:
    def __init__(self, title, entries):
        self.title: str = title
        self.entries: list[MenuItem] = entries
        self.index: int = 0

    def next_entry(self):
        self.index = (self.index + 1) % len(self.entries)

    def previous_entry(self):
        self.index = (self.index - 1) % len(self.entries)

    @property
    def current_entry(self) -> MenuItem:
        return self.entries[self.index]
