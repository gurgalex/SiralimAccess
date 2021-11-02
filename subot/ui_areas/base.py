from abc import abstractmethod, ABC, ABCMeta
import numpy as np
from numpy.typing import ArrayLike

class SpeakAuto(metaclass=ABCMeta):

    @abstractmethod
    def speak_auto(self):
        pass





