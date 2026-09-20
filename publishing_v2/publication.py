"""Keep review-only material and unresolved attribution out of public delivery."""

def image_without_public_credit(image):
    return (isinstance(image, dict)
            and image.get('license') in {'Public domain', 'CC0', 'CC0 1.0'}
            and not image.get('restrictions')
            and str(image.get('attribution_required', '')).lower() in {'', 'false', 'no'})


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
        if not image_without_public_credit(cards[i].get('image')):
            # CC BY remains available for review. It cannot be published with its
            # required attribution removed. Select a no-credit alternative first.
            raise ValueError('public_attribution_required')
    return indices
