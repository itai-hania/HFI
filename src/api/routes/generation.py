"""Generation and translation endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import require_jwt
from api.schemas.generation import (
    GeneratePostRequest,
    GeneratePostResponse,
    GenerateThreadRequest,
    GenerateThreadResponse,
    TranslateRequest,
    TranslateResponse,
)

router = APIRouter(
    prefix="/api/generation",
    tags=["generation"],
    dependencies=[Depends(require_jwt)],
)


def get_content_generator():
    """Factory kept separate for test patching."""
    from processor.content_generator import ContentGenerator

    return ContentGenerator()


def get_translation_service():
    """Factory kept separate for test patching."""
    from processor.processor import ProcessorConfig, TranslationService

    config = ProcessorConfig()
    return TranslationService(config)


def get_scraper():
    """Factory kept separate for test patching."""
    from scraper.scraper import TwitterScraper

    return TwitterScraper(headless=True)


@router.post("/post", response_model=GeneratePostResponse)
def generate_post(request: GeneratePostRequest):
    """Generate Hebrew post variants from source text."""
    generator = get_content_generator()
    variants = generator.generate_post(
        source_text=request.source_text,
        num_variants=request.num_variants,
        angles=request.angles,
    )
    return GeneratePostResponse(variants=variants)


@router.post("/thread", response_model=GenerateThreadResponse)
def generate_thread(request: GenerateThreadRequest):
    """Generate Hebrew thread variants from source text."""
    generator = get_content_generator()
    tweets = generator.generate_thread(
        source_text=request.source_text,
        num_tweets=request.num_tweets,
        angle=request.angle,
    )
    return GenerateThreadResponse(tweets=tweets)


@router.post("/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest):
    """Translate text directly or scrape then translate from a URL."""
    service = get_translation_service()

    original_text = request.text or ""
    source_type = "text"

    if request.url:
        source_type = "url"
        scraper = get_scraper()
        try:
            await scraper.ensure_logged_in()
            tweet_data = await scraper.get_tweet_content(request.url)
            original_text = (tweet_data or {}).get("text", "")
        finally:
            await scraper.close()

    if not original_text:
        raise HTTPException(status_code=400, detail="No source text found")

    hebrew_text = await asyncio.to_thread(service.translate_and_rewrite, original_text)
    return TranslateResponse(
        hebrew_text=hebrew_text,
        original_text=original_text,
        source_type=source_type,
    )
