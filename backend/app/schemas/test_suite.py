from typing import List, Literal
from pydantic import BaseModel, Field

class TestFile(BaseModel):
    path: str = Field(description="Path where the test file should be written")
    content: str = Field(description="Full Python source code of the test file")
    test_type: Literal["unit", "integration"] = Field(description="Type of test")
    covers: List[str] = Field(description="List of source file paths this test file covers")

class TestSuite(BaseModel):
    framework: str = Field(default="pytest", description="Testing framework used")
    test_files: List[TestFile] = Field(description="List of test files in the suite")
