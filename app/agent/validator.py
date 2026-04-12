from app.agent.schemas import Plan

ALLOWED_TOOLS = {"get_order", "refund", "create_ticket"}
ALLOWED_ACTIONS = {"tool", "rag", "respond"}


class PlanValidator:

    def validate(self, plan: Plan):

        if not plan.steps:
            raise ValueError("Empty plan")

        for step in plan.steps:

            # ===== VALID ACTION =====
            if step.action not in ALLOWED_ACTIONS:
                raise ValueError(f"Invalid action: {step.action}")

            # ===== TOOL VALIDATION =====
            if step.action == "tool":

                if not step.tool_name:
                    raise ValueError("Tool step missing tool_name")

                if step.tool_name not in ALLOWED_TOOLS:
                    raise ValueError(f"Invalid tool: {step.tool_name}")

                # CRITICAL: enforce input
                if not step.input:
                    raise ValueError(f"{step.tool_name} missing input")

                if step.tool_name in ["get_order", "refund"]:
                    if "order_id" not in step.input:
                        raise ValueError(f"{step.tool_name} missing order_id")

            # ===== NON-TOOL MUST NOT HAVE TOOL =====
            if step.action != "tool" and step.tool_name:
                raise ValueError("Non-tool step cannot have tool_name")

        # ===== FINAL STEP =====
        if plan.steps[-1].action != "respond":
            raise ValueError("Last step must be respond")

        return True
