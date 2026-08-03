"""Minimal SETT 0.11 execution-context and trace example."""
from sett import ExecutionContext, SETTAgent, SETTExpert, SETTOrchestrator


class ClassifierExpert(SETTExpert):
    def resolve(self, context):
        value = int(context.get("value", 0))
        return {"value": value, "classification": "positive" if value > 0 else "other"}


class ClassificationAgent(SETTAgent):
    def __init__(self):
        super().__init__(name="ClassificationAgent", domain="classification")
        self.register_expert(ClassifierExpert("classifier"))

    def process(self, input_data):
        result = self.get_expert("classifier").resolve(input_data)
        self._publish_to_universal(result)
        return result


orchestrator = SETTOrchestrator()
orchestrator.register_agent(ClassificationAgent())

context = ExecutionContext.create(
    application_id="trace-example",
    metadata={"channel": "example"},
)
traced = orchestrator.process_traced(
    {"value": 4},
    domain="classification",
    execution_context=context,
)

print(traced.result)
for event in orchestrator.export_trace(traced.trace_id, view="summary"):
    print(event["sequence"], event["kind"], event["status"])

assert orchestrator.verify_traces(traced.trace_id)
