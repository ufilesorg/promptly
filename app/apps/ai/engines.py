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

    @property
    def image_price(self):
        return 85 * 1.5 / 1000

    @property
    def input_price(self):
        return 0.27

    @property
    def output_price(self):
        return 1.5

    @property
    def price(self):
        return self.input_price, self.output_price

    def get_price(self, input_tokens: int, output_tokens: int, image_count: int = 0):
        return (
            input_tokens * self.input_price / 1000
            + output_tokens * self.output_price / 1000
            + image_count * self.image_price
        )

    @classmethod
    def get_by_name(cls, name: str):
        for subclass in cls.__subclasses__():
            if subclass.__name__.lower() == name.lower():
                return subclass()
        raise ValueError(f"Unknown engine name: {name}")


class Perplexity(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("PERPLEXITY_API_KEY"), "https://api.perplexity.ai")

    @property
    def model(self):
        return [
            "sonar-pro",
            "sonar",
            "llama-3.1-sonar-huge-128k-online",
            "llama-3.1-sonar-large-128k-online",
            "llama-3.1-sonar-small-128k-online",
        ][1]

    @property
    def input_price(self):
        return 0.1

    @property
    def output_price(self):
        return 0.1


class Metis(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("METIS_API_KEY"), "https://api.metisai.ir/openai/v1")


class MetisVision(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("METIS_API_KEY"), "https://api.metisai.ir/openai/v1")

    @property
    def model(self):
        return "gpt-4o-mini"

    @property
    def input_price(self):
        return 0.02

    @property
    def output_price(self):
        return 0.07

    @property
    def image_price(self):
        return 85 * 1.5 / 1000


class AvvalAI(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("AVVALAI_API_KEY"), "https://api.avalai.ir/v1")

    @property
    def input_price(self):
        return 0.3

    @property
    def output_price(self):
        return 1.5


class Grok(AIEngine):
    def __init__(self):
        # super().__init__(os.getenv("GROK_API_KEY"), "https://api.x.ai/v1")
        super().__init__(os.getenv("METIS_API_KEY"), "https://api.metisai.ir/openai/v1")

    @property
    def model(self):
        return "grok-2"

    @property
    def input_price(self):
        return 0.25

    @property
    def output_price(self):
        return 1.5


class GeminiFlash(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("METIS_API_KEY"), "https://api.metisai.ir/openai/v1")

    @property
    def model(self):
        return "gemini-1.5-flash"

    @property
    def input_price(self):
        return 0.01

    @property
    def output_price(self):
        return 0.03

    @property
    def image_price(self):
        return 0.00004


class GeminiPro(AIEngine):
    def __init__(self):
        super().__init__(os.getenv("METIS_API_KEY"), "https://api.metisai.ir/openai/v1")

    @property
    def model(self):
        return "gemini-1.5-pro"

    @property
    def input_price(self):
        return 0.4

    @property
    def output_price(self):
        return 1.5

    @property
    def image_price(self):
        return 0.0006575
