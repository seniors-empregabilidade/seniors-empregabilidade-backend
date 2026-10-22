from pydantic import BaseModel


class SupportContactResponse(BaseModel):
    whatsapp_number: str
    initial_message: str
