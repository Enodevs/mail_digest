from pydantic import BaseModel, Field


class GetEmailsInput(BaseModel):
    query: str = Field(
        description="A Gmail search query used to find emails."
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of emails to retrieve."
    )
