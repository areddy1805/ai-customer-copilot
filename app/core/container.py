_orchestrator = None


def get_orchestrator():
    global _orchestrator

    if _orchestrator is None:
        print("INITIALIZING ORCHESTRATOR (LAZY)")
        from app.orchestrator.orchestrator import Orchestrator

        _orchestrator = Orchestrator()

    return _orchestrator
