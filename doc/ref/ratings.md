# Voting Data Algorithm

This spec defines two minimal Bayesian aggregation algorithms for spam-resistant item ranking. Both use 2-3 persisted numeric fields in human-readable JSON files, discarding raw vote logs after daily aggregation. Scores shrink sparse items toward neutral priors, converging to true population ratings at scale.

## Shared Properties
- **Persisted in JSON**: Under `"votes": { ... }` per item.
- **Daily process**: Log votes → compute sums → update fields → delete logs.
- **Prior strength**: `prior_weight = 10` (tunable; ~2 weeks baseline activity).
- **Ranking**: Sort items by `score` descending.

## A) Binary Likes (0D signal)

Tracks pure positive signals without dislikes/views.

### Data Shape
```json
"votes": {
  "rating": 12.4,    // Bayesian mean likes-per-day (float)
  "weight": 5        // Cumulative days active (int)
}
```

### Algorithm
**Formula**: `score = (sum_likes + prior_likes) / (weight + prior_weight)`

**Parameters**:
- `prior_likes = 3` (0.3 likes/day × 10)
- Neutral start: `3/10 = 0.3`

**Daily update**:
```
sum_likes += daily_like_count
weight += 1
rating = (sum_likes + 3) / (weight + 10)
```

**Example evolution**:
| Day | Daily Likes | Sum Likes | Weight | Score |
|-----|-------------|-----------|--------|--------|
| 0   | -           | 0         | 0      | 0.30  |
| 1   | 2           | 2         | 1      | 0.45  |
| 3   | 1           | 8         | 3      | 0.85  |
| 10  | 4 avg       | 35        | 10     | 2.91  |

## B) 0-10 Ratings (1D signal + spread)

Aggregates ratings with Bayesian mean and sample standard deviation.

### Data Shape
```json
"votes": {
  "rating": 6.2,        // Bayesian mean rating (0-10, float)
  "spread": 1.8,        // Bayesian std deviation (float) 
  "weight": 23          // Cumulative vote count (int)
}
```

### Algorithm
**Mean**: `mean = (sum_ratings + prior_weight × 5) / (weight + prior_weight)`

**Variance**: `var = [(sum_squares + prior_sum_squares) / total_weight] - mean²`  
**Spread**: `std_dev = √var`

**Parameters**:
- `prior_mean = 5.0` (scale midpoint)
- `prior_std = 2.0` (neutral spread)
- `prior_sum_squares = prior_weight × (5² + 2²) = 10 × 29 = 290`

**Daily update**:
```
sum_ratings += Σ(daily_ratings)
sum_squares += Σ(r_i²)
weight += daily_vote_count
mean = (sum_ratings + 50) / (weight + 10)
total_weight = weight + 10
var = (sum_squares + 290) / total_weight - mean²
spread = √var
```

### Example evolution

| Day | Votes (avg) | Weight | Mean | Spread |
|-----|-------------|--------|------|--------|
| 0   | -           | 0      | 5.0  | 2.0   |
| 1   | 5 (7.2)     | 5      | 5.73 | 1.58  |
| 3   | +1 (2.0)    | 9      | 5.65 | 2.10  |
| 5   | +4 (8.5)    | 16     | 5.81 | 2.32  |

## Ranking Rules
```
Primary: rating (descending)
Tiebreaker: spread (ascending, consensus wins)
Composite: rating - 0.3 × spread (penalize polarization)
```

## HN Spike Behavior
prior_weight=10 becomes negligible at 1000+ votes/day. Score converges to population mean within ~1% after 3-5 high-volume days.

**Storage**: 2-3 numbers per item. 64-bit floats handle millions of votes. JSON remains human-readable even at scale.