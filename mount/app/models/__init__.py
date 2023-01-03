import pydantic
import orjson

class BaseModel(pydantic.BaseModel):
    class Config:
        json_loads = orjson.loads
        json_dumps = orjson.dumps