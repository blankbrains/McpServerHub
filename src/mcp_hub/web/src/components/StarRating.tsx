interface StarRatingProps {
  rating: number
  maxRating?: number
  interactive?: boolean
  onChange?: (rating: number) => void
  size?: 'sm' | 'md' | 'lg'
  showValue?: boolean
  reviewCount?: number
}

const SIZE_CLASSES = {
  sm: 'text-sm',
  md: 'text-lg',
  lg: 'text-2xl',
}

export default function StarRating({
  rating,
  maxRating = 5,
  interactive = false,
  onChange,
  size = 'md',
  showValue = false,
  reviewCount,
}: StarRatingProps) {
  const stars = Array.from({ length: maxRating }, (_, i) => i + 1)

  const handleClick = (value: number) => {
    if (interactive && onChange) {
      onChange(value)
    }
  }

  return (
    <span
      className={`inline-flex items-center gap-0.5 ${SIZE_CLASSES[size]}`}
      role={interactive ? 'radiogroup' : undefined}
      aria-label={interactive ? '评分' : undefined}
      aria-valuenow={interactive ? Math.round(rating) : undefined}
      aria-valuemin={interactive ? 1 : undefined}
      aria-valuemax={interactive ? maxRating : undefined}
    >
      {stars.map(star => {
        const filled = star <= Math.round(rating)
        return (
          <button
            key={star}
            type="button"
            disabled={!interactive}
            role={interactive ? 'radio' : undefined}
            aria-checked={interactive ? star === Math.round(rating) : undefined}
            onClick={() => handleClick(star)}
            className={`${interactive ? 'cursor-pointer hover:scale-110 transition-transform' : 'cursor-default'} disabled:cursor-default`}
            aria-label={`${star} 星`}
          >
            {filled ? (
              <span className="text-yellow-400">★</span>
            ) : (
              <span className="text-gray-300">★</span>
            )}
          </button>
        )
      })}
      {showValue && (
        <span className="ml-1 text-sm text-gray-600 font-medium">
          {rating.toFixed(1)}
        </span>
      )}
      {reviewCount !== undefined && reviewCount > 0 && (
        <span className="ml-1 text-xs text-gray-400">
          ({reviewCount})
        </span>
      )}
    </span>
  )
}
