"""
Startup validation for ContextForge.

Validates configuration and system requirements before starting services.
Provides helpful error messages and recommendations.
"""

import sys
import logging
from typing import Optional
from pathlib import Path

# Configure basic logging for startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_startup(exit_on_error: bool = True) -> bool:
    """
    Validate system configuration at startup.
    
    Args:
        exit_on_error: If True, exit process on validation errors
        
    Returns:
        True if validation passed, False otherwise
    """
    logger.info("=" * 60)
    logger.info("ContextForge Startup Validation")
    logger.info("=" * 60)
    
    # Step 1: Validate configuration
    logger.info("\n[1/4] Validating configuration...")
    config_valid = _validate_config()
    
    # Step 2: Check dependencies
    logger.info("\n[2/4] Checking dependencies...")
    deps_valid = _check_dependencies()
    
    # Step 3: Validate execution strategy
    logger.info("\n[3/4] Validating execution strategy...")
    strategy_valid = _validate_execution_strategy()
    
    # Step 4: Initialize event bus
    logger.info("\n[4/4] Initializing event bus...")
    eventbus_valid = _initialize_event_bus()
    
    # Summary
    logger.info("\n" + "=" * 60)
    all_valid = config_valid and deps_valid and strategy_valid and eventbus_valid
    
    if all_valid:
        logger.info("✓ Startup validation PASSED")
        logger.info("=" * 60)
        return True
    else:
        logger.error("✗ Startup validation FAILED")
        logger.info("=" * 60)
        
        if exit_on_error:
            logger.error("Exiting due to validation errors. Fix the issues above and restart.")
            sys.exit(1)
        
        return False


def _validate_config() -> bool:
    """Validate configuration using ConfigValidator."""
    try:
        from services.config import get_config
        from services.config.validator import ConfigValidator
        
        config = get_config()
        validator = ConfigValidator(config)
        result = validator.validate_all()
        
        # Print errors
        if result.errors:
            logger.error(f"  Found {len(result.errors)} error(s):")
            for error in result.errors:
                logger.error(f"    ✗ {error}")
        
        # Print warnings
        if result.warnings:
            logger.warning(f"  Found {len(result.warnings)} warning(s):")
            for warning in result.warnings:
                logger.warning(f"    ⚠ {warning}")
        
        # Print info
        if result.info:
            for info in result.info:
                logger.info(f"    ℹ {info}")
        
        if result.valid:
            logger.info("  ✓ Configuration valid")
        
        return result.valid
        
    except Exception as e:
        logger.error(f"  ✗ Configuration validation failed: {e}")
        return False


def _check_dependencies() -> bool:
    """Check required dependencies."""
    required = {
        'fastapi': 'FastAPI',
        'pydantic': 'Pydantic',
        'structlog': 'structlog',
        'sentence_transformers': 'sentence-transformers',
    }
    
    optional = {
        'faiss': 'faiss-cpu (for vector search)',
        'tree_sitter': 'tree-sitter (for code parsing)',
    }
    
    all_valid = True
    
    # Check required
    for module, name in required.items():
        try:
            __import__(module)
            logger.info(f"  ✓ {name}")
        except ImportError:
            logger.error(f"  ✗ {name} not found - install with: pip install {module}")
            all_valid = False
    
    # Check optional
    for module, name in optional.items():
        try:
            __import__(module)
            logger.info(f"  ✓ {name}")
        except ImportError:
            logger.warning(f"  ⚠ {name} not found (optional)")
    
    return all_valid


def _validate_execution_strategy() -> bool:
    """Validate execution strategy configuration."""
    try:
        from services.core.execution_strategy import ExecutionStrategy, ExecutionResolver
        from services.config import get_config
        
        config = get_config()
        
        # Map operation mode to execution strategy
        mode_map = {
            'auto': ExecutionStrategy.HYBRID_AUTO,
            'online': ExecutionStrategy.CLOUD_PREFERRED,
            'offline': ExecutionStrategy.LOCAL_ONLY
        }
        
        # Get mode from config (default to auto)
        mode = getattr(config, 'operation_mode', 'auto')
        strategy = mode_map.get(mode, ExecutionStrategy.HYBRID_AUTO)
        
        resolver = ExecutionResolver(strategy)
        status = resolver.get_status()
        
        logger.info(f"  Strategy: {status['strategy']}")
        logger.info(f"  Online: {status['online']}")
        logger.info(f"  Cloud keys configured: {status['has_cloud_keys']}")
        logger.info(f"  Will use cloud LLM: {status['will_use_cloud_llm']}")
        
        if not status['online'] and strategy == ExecutionStrategy.CLOUD_PREFERRED:
            logger.warning("  ⚠ CLOUD_PREFERRED strategy but offline - will use local LLM")
        
        logger.info("  ✓ Execution strategy configured")
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Execution strategy validation failed: {e}")
        return False


def _initialize_event_bus() -> bool:
    """Initialize the event bus."""
    try:
        from services.core.event_bus import get_event_bus, EventType
        
        bus = get_event_bus()
        stats = bus.get_stats()
        
        logger.info(f"  Event types available: {len(EventType)}")
        logger.info(f"  ✓ Event bus initialized")
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Event bus initialization failed: {e}")
        return False


if __name__ == "__main__":
    validate_startup(exit_on_error=True)

