from typing import List, Literal
from pydantic import BaseModel, Field

class SprintTask(BaseModel):
    id: str = Field(description="Unique identifier for the task")
    title: str = Field(description="Title of the task")
    description: str = Field(description="Detailed description of the task")
    story_points: int = Field(description="Estimated story points for the task")
    type: Literal["frontend", "backend", "db", "infra"] = Field(description="Type of task")

class Sprint(BaseModel):
    id: str = Field(description="Unique identifier for the sprint")
    name: str = Field(description="Name of the sprint (e.g., Sprint 1)")
    goal: str = Field(description="The primary goal of this sprint")
    duration_days: int = Field(description="Duration of the sprint in days")
    stories: List[str] = Field(description="List of user story IDs included in this sprint")
    tasks: List[SprintTask] = Field(description="List of tasks to be completed in this sprint")

class SprintPlan(BaseModel):
    sprints: List[Sprint] = Field(description="List of sprints planned")
