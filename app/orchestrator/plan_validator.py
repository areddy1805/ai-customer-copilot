from app.orchestrator.plan_schema import Plan


class PlanValidator:

    def validate(self, plan: Plan):

        if not plan.steps:
            return None, "Empty plan"

        step_ids = set()

        # -----------------------------
        # BASIC STRUCTURE VALIDATION
        # -----------------------------
        for step in plan.steps:

            # step_id must exist
            if step.step_id is None:
                return None, "Missing step_id"

            # uniqueness
            if step.step_id in step_ids:
                return None, f"Duplicate step_id: {step.step_id}"

            step_ids.add(step.step_id)

            # action must be "tool" or "respond"
            if step.action not in {"tool", "respond"}:
                return None, f"Invalid action: {step.action}"

            # tool steps must have tool_name
            if step.action == "tool" and not step.tool_name:
                return None, f"Missing tool_name in step {step.step_id}"

        # -----------------------------
        # DEPENDENCY VALIDATION
        # -----------------------------
        for step in plan.steps:

            for dep in step.depends_on:

                if dep not in step_ids:
                    return None, f"Invalid dependency {dep} in step {step.step_id}"

                if dep == step.step_id:
                    return None, f"Self dependency in step {step.step_id}"

        # -----------------------------
        # CYCLE DETECTION (DFS)
        # -----------------------------
        graph = {step.step_id: step.depends_on for step in plan.steps}

        visited = set()
        visiting = set()

        def dfs(node):
            if node in visiting:
                return True  # cycle

            if node in visited:
                return False

            visiting.add(node)

            for dep in graph.get(node, []):
                if dfs(dep):
                    return True

            visiting.remove(node)
            visited.add(node)
            return False

        for node in graph:
            if dfs(node):
                return None, "Cycle detected in plan"

        # -----------------------------
        # STEP LIMIT
        # -----------------------------
        if len(plan.steps) > 3:
            return None, "Too many steps"

        return plan, None
