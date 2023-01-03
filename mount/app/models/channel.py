from app.models import BaseModel


class Channel(BaseModel):
    name: str
    description: str
    public_read: bool
    public_write: bool
    moderated: bool
    instance: bool
