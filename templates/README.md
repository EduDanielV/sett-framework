# Templates

Starting point for creating your own agent and experts. Copy, rename,
fill in the `TODO`s. Both templates, as they are, are real code — they
can be instantiated and run without filling in anything, so if
something fails right after copying them, the problem is with your
import, not the template.

## Recommended order

1. Copy `expert_template.py` once for each specific task your domain
   needs to resolve (one, two, five — the number is defined by your
   domain, not a fixed rule).
2. Copy `agent_template.py` once, and register the experts you wrote
   in step 1 there.
3. Inside the agent's `process()`, pick **one** of the three ways to
   close it — they're explained in the file itself. Quick rule:
   - Does your agent only report a state? → option (A).
   - Does it execute something real (message, API) but you're
     prototyping quickly? → option (B), `propose_action`.
   - Does it execute something real and you want the full structural
     guarantee (the agent never touches the real client)? → option
     (C), `submit_action` + a `SETTExecutor` with a registered handler.
4. `orchestrator.register_agent(YourAgent())`. Done.

To remove an agent from the system: don't call `register_agent()`
with it. There's nothing else to disconnect.

For the full explanation of each class, see `docs/api_reference.md`.
To understand the reasoning behind the three risk layers and the
ethical filter, see `docs/concepts.md`.
