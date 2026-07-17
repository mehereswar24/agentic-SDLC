"""Pydantic schemas for agent inputs and outputs."""

from app.schemas.clarifying_questions import ClarifyingQuestion, ClarifyingQuestions
from app.schemas.critique import Critique
from app.schemas.design import Component, DataModel, SystemDesign
from app.schemas.prd import (
    PRD,
    AcceptanceCriterion,
    AssumptionRegister,
    FunctionalRequirement,
    NonFunctionalRequirement,
    Persona,
    Priority,
    Risk,
    Severity,
    SuccessMetric,
    UserStory,
)
from app.schemas.sprint_plan import Sprint, SprintPlan, SprintTask
from app.schemas.test_suite import TestFile, TestSuite
from app.schemas.validation import ValidationReport

__all__ = [
    "PRD",
    "AcceptanceCriterion",
    "AssumptionRegister",
    "ClarifyingQuestion",
    "ClarifyingQuestions",
    "Component",
    "Critique",
    "DataModel",
    "FunctionalRequirement",
    "NonFunctionalRequirement",
    "Persona",
    "Priority",
    "Risk",
    "Severity",
    "SuccessMetric",
    "SystemDesign",
    "UserStory",
    "Sprint",
    "SprintPlan",
    "SprintTask",
    "TestFile",
    "TestSuite",
    "ValidationReport",
]
