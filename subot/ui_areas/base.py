from abc import abstractmethod, ABC, ABCMeta


class SpeakAuto(metaclass=ABCMeta):

    @abstractmethod
    def speak_auto(self):
        pass



