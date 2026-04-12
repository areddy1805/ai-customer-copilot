class AgentPlanner:

    def optimize(self, plan, tasks):
        """
        Optional optimization layer.

        Allowed:
        - reorder independent steps
        - merge duplicate steps
        - parallelization hints

        Not allowed:
        - change intent
        - remove required dependencies
        """

        # Example: remove duplicate get_order calls
        seen = set()
        new_steps = []

        for step in plan.steps:
            key = (step.tool_name, str(step.input))

            if key in seen:
                continue

            seen.add(key)
            new_steps.append(step)

        plan.steps = new_steps

        return plan
