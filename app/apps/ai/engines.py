import os

from singleton import Singleton


class AIEngine(metaclass=Singleton):
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    def get_dict(self):
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
        }

    @property
    def model(self):
        return "gpt-4o"

    @classmethod
    def get_by_name(cls, name: str):
        for subclass in cls.__subclasses__():
            if subclass.__name__.lower() == name.lower():
                return subclass()


class Perplexity(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("PERPLEXITY_API_KEY"), "https://api.perplexity.ai")

    @property
    def model(self):
        return [
            "llama-3.1-sonar-huge-128k-online",
            "llama-3.1-sonar-large-128k-online",
            "llama-3.1-sonar-small-128k-online",
        ][1]


class Metis(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("METIS_API_KEY"), "https://api.metisai.ir/openai/v1")


class AvvalAI(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("AVVALAI_API_KEY"), "https://api.avalai.ir/v1")


class Grok(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("GROK_API_KEY"), "https://api.x.ai/v1")

    @property
    def model(self):
        return "grok-beta"
