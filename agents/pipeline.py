from agents.base import get_agent_logger
from agents.validation import validate_context, create_default_context
from agents.trend_analyst import TrendAnalystAgent
from agents.copywriter import CopywriterAgent
from agents.fact_checker import FactCheckerAgent
from agents.publisher import PublisherAgent

class Pipeline:
    def __init__(self):
        self.logger = get_agent_logger("daemon")
        self.agents = []

    def register(self, agent):
        self.logger.info(f"Registered agent: {agent.name}")
        # To avoid duplicating agents if they are explicitly registered
        self.agents = [a for a in self.agents if a.name != agent.name]
        self.agents.append(agent)

    def run(self, context: dict = None) -> dict:
        if context is None:
            context = create_default_context()
        else:
            # First validate context to ensure it conforms to required schema
            validate_context(context, partial=True)
            
            # Merge with defaults
            default_ctx = create_default_context()
            for k, v in default_ctx.items():
                if k not in context:
                    context[k] = v
                    
            # Auto-populate default agents if agents list is empty
            if not self.agents:
                self.register(TrendAnalystAgent())
                self.register(CopywriterAgent())
                self.register(FactCheckerAgent())
                self.register(PublisherAgent())
                
        self.logger.info("Starting Auto-Blogging Pipeline execution.")
        
        # Validation on start
        validate_context(context)
        
        try:
            for agent in self.agents:
                self.logger.info(f"Executing agent: {agent.name}...")
                context = agent.execute(context)
                validate_context(context)
                
            self.logger.info("Pipeline executed successfully.")
        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}")
            raise e
            
        return context
