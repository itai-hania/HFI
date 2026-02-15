import logging

logger = logging.getLogger(__name__)

_style_manager = None
_summary_generator = None
_auto_pipeline = None


def get_style_manager():
    """Lazy load style manager functions (cached)."""
    global _style_manager
    if _style_manager is not None:
        return _style_manager
    try:
        from processor import style_manager
        _style_manager = style_manager
        return _style_manager
    except Exception as e:
        logger.warning(f"Could not load style_manager: {e}")
        return None


def get_summary_generator():
    """Lazy load summary generator (cached singleton)."""
    global _summary_generator
    if _summary_generator is not None:
        return _summary_generator
    try:
        from processor.summary_generator import SummaryGenerator
        _summary_generator = SummaryGenerator()
        return _summary_generator
    except Exception as e:
        logger.warning(f"Could not initialize SummaryGenerator: {e}")
        return None


def get_auto_pipeline():
    """Lazy load AutoPipeline (cached singleton)."""
    global _auto_pipeline
    if _auto_pipeline is not None:
        return _auto_pipeline
    try:
        from processor.auto_pipeline import AutoPipeline
        _auto_pipeline = AutoPipeline()
        return _auto_pipeline
    except Exception as e:
        logger.warning(f"Could not initialize AutoPipeline: {e}")
        return None
