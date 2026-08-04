from abc import ABC, abstractmethod

class BaseEngine(ABC):
    @property
    def __init__(self):
        self._is_connected = False

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def is_connected(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def insert(self,  data):
        pass

    @abstractmethod
    def delete_record(self, record_id):
        pass

    @abstractmethod
    def delete_filter(self, filter):
        pass

    @abstractmethod
    def get_by_id(self, record_id):
        pass

    def __enter__(self):
        self.connect()

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()
