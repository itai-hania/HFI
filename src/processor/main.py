"""
Main entry point for the Processor service.

This script runs a simple polling loop that:
1. Checks for pending tweets every 30 seconds
2. Processes them (translate + download media)
3. Updates database status
4. Repeats indefinitely

Architecture Decision: Simple Polling vs. Celery
------------------------------------------------
We chose a simple polling loop instead of Celery for several reasons:

1. **Simplicity**: No Redis/RabbitMQ dependency, easier to deploy
2. **Self-contained**: Everything in one process, easier to debug
3. **Resource efficiency**: Low volume (dozens of tweets/hour, not thousands)
4. **Reliability**: Simpler = fewer failure modes
5. **Kubernetes-friendly**: Can scale horizontally if needed (multiple replicas)

When to switch to Celery:
- Processing >1000 tweets/hour
- Need priority queues
- Complex task dependencies
- Distributed workers across machines

For this use case (scraping fintech news, dozens of tweets/hour),
simple polling is more appropriate than heavyweight task queue systems.

Error Handling Strategy:
- Individual tweet failures don't crash the service
- Database connection errors trigger exponential backoff
- Keyboard interrupt (Ctrl+C) gracefully shuts down
- All errors logged with timestamps for debugging
"""

import os
import time
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from processor import TweetProcessor
from common.models import create_tables

# Configure logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(Path(os.getenv('LOG_DIR', str(Path(__file__).parent.parent.parent / 'data'))) / 'processor.log'))
    ]
)
logger = logging.getLogger(__name__)


class ProcessorService:
    """
    Service wrapper for the processor with graceful shutdown handling.

    Manages the lifecycle of the processor:
    - Initialization
    - Continuous polling loop
    - Graceful shutdown on SIGTERM/SIGINT
    - Error recovery with exponential backoff
    """

    def __init__(self, poll_interval: int = 30):
        """
        Initialize the processor service.

        Args:
            poll_interval: Seconds to wait between polling cycles (default: 30)
        """
        self.poll_interval = poll_interval
        self.processor: Optional[TweetProcessor] = None
        self.running = False
        self.consecutive_errors = 0
        self.max_consecutive_errors = 10

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self.running = False

    def _calculate_backoff(self) -> int:
        """
        Calculate exponential backoff delay based on consecutive errors.

        Returns:
            Seconds to wait before retry

        Exponential backoff prevents hammering external services when they're down:
        - 0 errors: 30s (normal poll interval)
        - 1 error: 30s
        - 2 errors: 60s
        - 3 errors: 120s
        - 4+ errors: 300s (5 minutes)
        """
        if self.consecutive_errors == 0:
            return self.poll_interval

        # Exponential backoff: 30 * 2^(errors-1), capped at 300s
        backoff = min(self.poll_interval * (2 ** (self.consecutive_errors - 1)), 300)
        return backoff

    def run(self):
        """
        Main service loop - continuously poll for pending tweets.

        This method runs indefinitely until:
        - Shutdown signal received (SIGTERM/SIGINT)
        - Too many consecutive errors (fail-safe)
        """
        logger.info("=" * 60)
        logger.info("Processor Service Starting")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Log file: /Users/itayy16/CursorProjects/HFI/data/processor.log")
        logger.info("=" * 60)

        # Ensure database is initialized
        try:
            create_tables()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            logger.error("Cannot start service without database. Exiting.")
            sys.exit(1)

        # Initialize processor
        try:
            self.processor = TweetProcessor()
            logger.info("TweetProcessor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize processor: {e}")
            logger.error("Check OPENAI_API_KEY and config files. Exiting.")
            sys.exit(1)

        # Start polling loop
        self.running = True
        cycle_count = 0

        while self.running:
            cycle_count += 1
            cycle_start = datetime.now()

            logger.info(f"\n{'='*60}")
            logger.info(f"Cycle #{cycle_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")

            try:
                # Process pending tweets
                processed_count = self.processor.process_pending_tweets()

                # Log results
                if processed_count > 0:
                    logger.info(f"✓ Successfully processed {processed_count} tweet(s)")
                else:
                    logger.info("✓ No pending tweets to process")

                # Reset error counter on success
                self.consecutive_errors = 0

                # Calculate processing time
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                logger.info(f"Cycle completed in {cycle_duration:.2f} seconds")

            except KeyboardInterrupt:
                # User pressed Ctrl+C
                logger.info("Keyboard interrupt received")
                break

            except Exception as e:
                # Log error and increment counter
                self.consecutive_errors += 1
                logger.error(f"✗ Error in processing cycle: {e}", exc_info=True)
                logger.error(f"Consecutive errors: {self.consecutive_errors}/{self.max_consecutive_errors}")

                # Check if we've hit the error limit
                if self.consecutive_errors >= self.max_consecutive_errors:
                    logger.critical(
                        f"Reached maximum consecutive errors ({self.max_consecutive_errors}). "
                        "Service may be unhealthy. Shutting down."
                    )
                    break

            # Sleep before next cycle (with exponential backoff if errors)
            if self.running:
                wait_time = self._calculate_backoff()

                if self.consecutive_errors > 0:
                    logger.warning(
                        f"Backing off due to errors. "
                        f"Waiting {wait_time}s before next cycle..."
                    )
                else:
                    logger.info(f"Waiting {wait_time}s before next cycle...")

                # Sleep in 1-second intervals to allow quick shutdown
                for _ in range(wait_time):
                    if not self.running:
                        break
                    time.sleep(1)

        # Service stopped
        logger.info("\n" + "="*60)
        logger.info("Processor Service Stopped")
        logger.info(f"Total cycles completed: {cycle_count}")
        logger.info("="*60)


def main():
    """
    Main entry point for the processor service.

    Environment Variables:
    - OPENAI_API_KEY (required): OpenAI API key for translation
    - DATABASE_URL (optional): SQLite database path
    - PROCESSOR_POLL_INTERVAL (optional): Seconds between polls (default: 30)
    """
    import os

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Check required environment variables
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY environment variable is required")
        logger.error("Set it in .env file or export OPENAI_API_KEY=sk-...")
        sys.exit(1)

    # Get poll interval from environment (default: 30 seconds)
    poll_interval = int(os.getenv('PROCESSOR_POLL_INTERVAL', '30'))

    # Create and run service
    try:
        service = ProcessorService(poll_interval=poll_interval)
        service.run()
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
