from app.orchestrator.plan import Plan, Step
from app.orchestrator.constants import ALLOWED_ACTIONS


class PlanValidator:

    def validate(self, plan: Plan):

        valid_steps = []

        for step in plan.steps:
            if step.action in ALLOWED_ACTIONS:
                valid_steps.append(step)

        if not valid_steps:
            return None, "No valid steps"

        if len(valid_steps) > 3:
            return None, "Too many steps"

        return Plan(valid_steps, query=plan.query), None
