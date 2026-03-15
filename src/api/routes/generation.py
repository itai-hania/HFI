"""Generation and translation endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import require_jwt
from api.schemas.generation import (
    GeneratePostRequest,
    GeneratePostResponse,
    GenerateThreadRequest,
    GenerateThreadResponse,
    SourceResolveRequest,
    SourceResolveResponse,
    TranslateRequest,
    TranslateResponse,
)
from common.source_resolver import (
    SourceResolverError,
    SourceSessionError,
    SourceTimeoutError,
    resolve_source_input,
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

@router.post("/post", response_model=GeneratePostResponse)
def generate_post(request: GeneratePostRequest):
    """Generate Hebrew post variants from source text."""
    generator = get_content_generator()
    variants = generator.generate_post(
        source_text=request.source_text,
        num_variants=request.num_variants,
        angles=request.angles,
        use_tweet_types=request.use_tweet_types,
        tweet_types=request.tweet_types,
        humanize=request.humanize,
        quality_gate=request.quality_gate,
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


@router.post("/source/resolve", response_model=SourceResolveResponse)
async def resolve_source(request: SourceResolveRequest):
    """Resolve text or URL source into canonical generation input."""
    try:
        resolved = await resolve_source_input(text=request.text, url=request.url)
    except SourceSessionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SourceTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except SourceResolverError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SourceResolveResponse(**resolved.to_dict())


@router.post("/translate", response_model=TranslateResponse)
async def translate(request: TranslateRequest):
    """Translate text directly or resolve text from URL, then translate."""
    service = get_translation_service()

    try:
        resolved = await resolve_source_input(text=request.text, url=request.url)
    except SourceSessionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SourceTimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except SourceResolverError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    hebrew_text = await asyncio.to_thread(service.translate_and_rewrite, resolved.original_text)
    return TranslateResponse(
        hebrew_text=hebrew_text,
        original_text=resolved.original_text,
        source_type=resolved.source_type,
        title=resolved.title,
        canonical_url=resolved.canonical_url,
        source_domain=resolved.source_domain,
        preview_text=resolved.preview_text,
    )
