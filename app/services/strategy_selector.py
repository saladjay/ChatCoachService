"""
Strategy Selector Service

Provides random strategy selection based on scenario recommendations.
Strategies are loaded from config/strategy_mappings.yaml.
"""

import random
import logging
from pathlib import Path
from typing import List
import yaml

logger = logging.getLogger(__name__)


class StrategySelector:
    """Service for selecting random strategies based on scenario."""
    
    def __init__(self, config_path: str = "config/strategy_mappings.yaml"):
        """
        Initialize the strategy selector.
        
        Args:
            config_path: Path to the strategy mappings YAML file
        """
        self.config_path = Path(config_path)
        self.strategies = self._load_strategies()
    
    def _load_strategies(self) -> dict:
        """
        Load strategy mappings from YAML file.
        
        Returns:
            Dictionary mapping scenario names to strategy lists
        """
        try:
            if not self.config_path.exists():
                logger.error(f"Strategy config file not found: {self.config_path}")
                return self._get_default_strategies()
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            strategies = config.get('strategies', {})
            logger.info(f"Loaded strategies for {len(strategies)} scenarios")
            return strategies
            
        except Exception as e:
            logger.error(f"Error loading strategy config: {e}")
            return self._get_default_strategies()
    
    def _get_default_strategies(self) -> dict:
        """
        Get default strategy mappings as fallback.
        
        Returns:
            Default strategy dictionary
        """
        return {
            "SAFE": [
                "situational_comment", "light_humor", "neutral_open_question",
                "shared_experience_probe", "empathetic_ack", "pace_matching"
            ],
            "BALANCED": [
                "playful_tease", "direct_compliment", "emotional_resonance",
                "perspective_flip", "value_signal", "micro_challenge"
            ],
            "RISKY": [
                "sexual_hint", "dominant_lead", "strong_frame_control",
                "bold_assumption", "fast_escalation", "taboo_play"
            ],
            "RECOVERY": [
                "tension_release", "boundary_respect", "misstep_repair",
                "emotional_deescalation", "graceful_exit"
            ],
            "NEGATIVE": [
                "validation_seeking", "logical_interview", "over_explaining",
                "neediness_signal", "performative_niceness"
            ]
        }
    
    def select_strategies(
        self,
        scenario: str,
        count: int = 3,
        seed: int | None = None
    ) -> List[str]:
        """
        Select random strategies for a given scenario.
        
        Args:
            scenario: Scenario name (SAFE, BALANCED, RISKY, RECOVERY, NEGATIVE)
            count: Number of strategies to select (default: 3)
            seed: Optional random seed for reproducibility
            
        Returns:
            List of selected strategy codes
        """
        # Normalize scenario name
        scenario = scenario.upper().strip()
        
        # Get strategies for this scenario
        available_strategies = self.strategies.get(scenario, [])
        
        if not available_strategies:
            logger.warning(f"No strategies found for scenario: {scenario}")
            # Fallback to SAFE strategies
            available_strategies = self.strategies.get("SAFE", [])
        
        # Set random seed if provided
        if seed is not None:
            random.seed(seed)
        
        # Select random strategies
        # If count > available, return all available strategies
        if count >= len(available_strategies):
            selected = available_strategies.copy()
            random.shuffle(selected)
            return selected
        
        # Otherwise, randomly sample
        selected = random.sample(available_strategies, count)
        
        logger.debug(
            f"Selected {len(selected)} strategies for scenario '{scenario}': {selected}"
        )
        
        return selected
    
    def get_all_strategies(self, scenario: str) -> List[str]:
        """
        Get all available strategies for a scenario.
        
        Args:
            scenario: Scenario name
            
        Returns:
            List of all strategy codes for the scenario
        """
        scenario = scenario.upper().strip()
        return self.strategies.get(scenario, [])
    
    def get_available_scenarios(self) -> List[str]:
        """
        Get list of all available scenario names.
        
        Returns:
            List of scenario names
        """
        return list(self.strategies.keys())


# Global instance
_strategy_selector = None


def get_strategy_selector() -> StrategySelector:
    """Get the global strategy selector instance."""
    global _strategy_selector
    if _strategy_selector is None:
        _strategy_selector = StrategySelector()
    return _strategy_selector
