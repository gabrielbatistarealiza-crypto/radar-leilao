from abc import ABC, abstractmethod

class BaseScraper(ABC):

    @abstractmethod
    def executar(self):
        pass
