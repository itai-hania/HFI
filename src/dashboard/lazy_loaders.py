import logging

logger = logging.getLogger(__name__)


def get_style_manager():
    """Lazy load style manager functions."""
    try:
        from processor import style_manager
        return style_manager
    except Exception as e:
        logger.warning(f"Could not load style_manager: {e}")
        return None


def get_summary_generator():
    """Lazy load summary generator to avoid import errors."""
    try:
        from processor.summary_generator import SummaryGenerator
        return SummaryGenerator()
    except Exception as e:
        logger.warning(f"Could not initialize SummaryGenerator: {e}")
        return None


def get_auto_pipeline():
    """Lazy load AutoPipeline with shared sub-components."""
    try:
        from processor.auto_pipeline import AutoPipeline
        return AutoPipeline()
    except Exception as e:
        logger.warning(f"Could not initialize AutoPipeline: {e}")
        return None
