"""Keep review-only material and unresolved attribution out of public delivery."""

def image_without_public_credit(image):
    from .official_images import owner_editorial_use
    return owner_editorial_use(image) or (isinstance(image, dict)
            and image.get('license') in {'Public domain', 'CC0', 'CC0 1.0'}
            and not image.get('restrictions')
            and str(image.get('attribution_required', '')).lower() in {'', 'false', 'no'})


def image_publication_eligible(image):
    from .autopilot.credits import public_attribution_eligible
    return image_without_public_credit(image) or public_attribution_eligible(image)


def validate_public_attribution(card, raw=None):
    import hashlib
    from .autopilot.credits import attribution_identity, public_attribution_eligible
    image = card.get('image')
    if image_without_public_credit(image):
        return
    receipt = card.get('public_attribution', {})
    if (not public_attribution_eligible(image) or receipt.get('version') != 1
            or receipt.get('image_sha256') != attribution_identity(image)
            or not isinstance(receipt.get('media_sha256'), str)
            or len(receipt['media_sha256']) != 64):
        raise ValueError('public_attribution_required')
    if raw is not None and hashlib.sha256(raw).hexdigest() != receipt['media_sha256']:
        raise ValueError('public_attribution_media_changed')


def publication_indices(cards):
    if not cards or any(card.get('kind') not in {'info', 'story', 'credits'} for card in cards):
        raise ValueError('explicit_media_kind_required')
    credits = [i for i, card in enumerate(cards) if card['kind'] == 'credits']
    if credits and credits != [len(cards)-1]:
        raise ValueError('review_credits_must_be_last')
    indices = [i for i, card in enumerate(cards) if card['kind'] != 'credits']
    if not indices:
        raise ValueError('no_editorial_media')
    for i in indices:
        validate_public_attribution(cards[i])
    return indices
