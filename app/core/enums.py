from enum import Enum


class Language(str, Enum):
    English = "English"
    Persian = "Persian"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_
