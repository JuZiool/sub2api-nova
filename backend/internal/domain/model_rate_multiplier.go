package domain

// ModelRateMultiplierRule defines one group-level user billing multiplier rule.
// Pattern supports an exact model name or a suffix wildcard (for example "gpt-5.6-*").
type ModelRateMultiplierRule struct {
	Pattern    string  `json:"pattern"`
	Multiplier float64 `json:"multiplier"`
}
