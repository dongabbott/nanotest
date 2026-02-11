from __future__ import annotations

from .models import StepExecution, TestCase


class MobileExecutionEngine:
    def run(self, testcase: TestCase) -> list[StepExecution]:
        route = testcase.route
        results: list[StepExecution] = []
        for step in testcase.steps:
            if step.action == "launch":
                route = testcase.route
            elif step.action == "tap" and step.target:
                route = f"{route.rstrip('/')}/{step.target}".replace("//", "/")
            results.append(
                StepExecution(
                    step_id=step.id,
                    status="passed",
                    message=f"Executed {step.action}",
                    route=route,
                )
            )
        return results


class AndroidUIA2Engine(MobileExecutionEngine):
    name = "Android: Appium/UIA2"


class IOSXCUITestEngine(MobileExecutionEngine):
    name = "iOS: XCUITest/Appium"


def get_engine(platform: str) -> MobileExecutionEngine:
    if platform == "android":
        return AndroidUIA2Engine()
    if platform == "ios":
        return IOSXCUITestEngine()
    raise ValueError(f"Unknown platform {platform}")
