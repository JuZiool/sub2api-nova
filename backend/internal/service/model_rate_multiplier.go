package service

import (
	"errors"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"github.com/Wei-Shaw/sub2api/internal/domain"
)

const maxModelRateMultiplierRules = 200
const maxModelRateMultiplier = 1000.0

// ModelRateMultiplierRule is the group-level model pricing rule persisted in groups.model_rate_multipliers.
type ModelRateMultiplierRule = domain.ModelRateMultiplierRule

// RateResolution is the immutable user-side multiplier decision for one request.
// It must be created before account model mapping and reused by every synchronous
// or asynchronous billing stage of the same request.
type RateResolution struct {
	PricingGroupID     int64
	PricingOwnerSource string
	RequestedModel     string
	MatchModel         string
	BaseMultiplier     float64
	TokenMultiplier    float64
	ImageMultiplier    float64
	VideoMultiplier    float64
	RateRuleSource     string
	RateRuleKey        string
	RateConfigVersion  int64
}

// RoutingResolution contains routing-only information. It is deliberately separate
// from RateResolution so upstream model mapping can never change user billing rules.
type RoutingResolution struct {
	Platform         string
	AccountID        int64
	MappedModel      string
	UpstreamModel    string
	CompositeRouteID *int64
	RouteSource      string
}

func NormalizeModelRateMatchModel(model string) string {
	return strings.TrimSpace(model)
}

// NormalizeModelRateMultiplierRules validates, canonicalizes and sorts rules so
// all callers get deterministic matching and API output.
func NormalizeModelRateMultiplierRules(rules []ModelRateMultiplierRule) ([]ModelRateMultiplierRule, error) {
	if len(rules) == 0 {
		return []ModelRateMultiplierRule{}, nil
	}
	if len(rules) > maxModelRateMultiplierRules {
		return nil, fmt.Errorf("model rate rules must not exceed %d entries", maxModelRateMultiplierRules)
	}

	seen := make(map[string]struct{}, len(rules))
	normalized := make([]ModelRateMultiplierRule, 0, len(rules))
	for _, rule := range rules {
		pattern := NormalizeModelRateMatchModel(rule.Pattern)
		if pattern == "" {
			return nil, errors.New("model rate rule pattern is required")
		}
		starCount := strings.Count(pattern, "*")
		if starCount > 1 || (starCount == 1 && !strings.HasSuffix(pattern, "*")) {
			return nil, fmt.Errorf("model rate rule %q only supports a trailing wildcard", pattern)
		}
		if pattern == "*" {
			return nil, errors.New("model rate rule wildcard prefix is required")
		}
		if math.IsNaN(rule.Multiplier) || math.IsInf(rule.Multiplier, 0) || rule.Multiplier <= 0 || rule.Multiplier > maxModelRateMultiplier {
			return nil, fmt.Errorf("model rate rule %q multiplier must be within (0, %g]", pattern, maxModelRateMultiplier)
		}
		if _, exists := seen[pattern]; exists {
			return nil, fmt.Errorf("duplicate model rate rule %q", pattern)
		}
		seen[pattern] = struct{}{}
		normalized = append(normalized, ModelRateMultiplierRule{Pattern: pattern, Multiplier: rule.Multiplier})
	}

	sort.Slice(normalized, func(i, j int) bool {
		return normalized[i].Pattern < normalized[j].Pattern
	})
	return normalized, nil
}

// ResolveRateResolution applies the only supported multiplier precedence:
// user-group override -> exact model -> longest trailing-wildcard prefix -> group default.
func ResolveRateResolution(group *Group, userGroupOverride *float64, requestedModel string, pricingAt time.Time) (*RateResolution, error) {
	if group == nil || group.ID <= 0 {
		return nil, errors.New("pricing group is required")
	}
	matchModel := NormalizeModelRateMatchModel(requestedModel)
	if matchModel == "" {
		return nil, errors.New("requested model is required")
	}
	if pricingAt.IsZero() {
		pricingAt = time.Now().UTC()
	}

	base := group.RateMultiplier
	source := "group_default"
	key := ""
	if userGroupOverride != nil {
		if !validModelRateMultiplier(*userGroupOverride) {
			return nil, errors.New("user group rate multiplier is invalid")
		}
		base = *userGroupOverride
		source = "user_group_override"
	} else {
		rules, err := NormalizeModelRateMultiplierRules(group.ModelRateMultipliers)
		if err != nil {
			return nil, fmt.Errorf("group model rate rules are invalid: %w", err)
		}
		if multiplier, matchedKey, ok := resolveModelRateRule(rules, matchModel); ok {
			base = multiplier
			key = matchedKey
			if strings.HasSuffix(matchedKey, "*") {
				source = "model_prefix"
			} else {
				source = "model_exact"
			}
		}
	}
	if !validModelRateMultiplier(base) {
		return nil, errors.New("group default rate multiplier is invalid")
	}

	imageMultiplier := base
	if group.ImageRateIndependent {
		imageMultiplier *= group.ImageRateMultiplier
	}
	videoMultiplier := base
	if group.VideoRateIndependent {
		videoMultiplier *= group.VideoRateMultiplier
	}
	if !validModelRateMultiplier(imageMultiplier) || !validModelRateMultiplier(videoMultiplier) {
		return nil, errors.New("group media rate multiplier is invalid")
	}

	version := group.RateConfigVersion
	if version <= 0 {
		version = 1
	}
	return &RateResolution{
		PricingGroupID:     group.ID,
		PricingOwnerSource: "authenticated_group",
		RequestedModel:     requestedModel,
		MatchModel:         matchModel,
		BaseMultiplier:     base,
		TokenMultiplier:    base * group.PeakMultiplierAt(pricingAt),
		ImageMultiplier:    imageMultiplier,
		VideoMultiplier:    videoMultiplier,
		RateRuleSource:     source,
		RateRuleKey:        key,
		RateConfigVersion:  version,
	}, nil
}

func resolveModelRateRule(rules []ModelRateMultiplierRule, model string) (float64, string, bool) {
	for _, rule := range rules {
		if !strings.HasSuffix(rule.Pattern, "*") && rule.Pattern == model {
			return rule.Multiplier, rule.Pattern, true
		}
	}
	var best *ModelRateMultiplierRule
	for i := range rules {
		rule := &rules[i]
		if !strings.HasSuffix(rule.Pattern, "*") {
			continue
		}
		prefix := strings.TrimSuffix(rule.Pattern, "*")
		if strings.HasPrefix(model, prefix) && (best == nil || len(prefix) > len(strings.TrimSuffix(best.Pattern, "*"))) {
			best = rule
		}
	}
	if best == nil {
		return 0, "", false
	}
	return best.Multiplier, best.Pattern, true
}

func validModelRateMultiplier(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0) && value > 0 && value <= maxModelRateMultiplier
}

// ApplyRateResolutionToUsageLog copies the immutable request pricing decision into
// the append-only usage log. Keeping it as explicit fields makes later billing
// reconciliation independent of changed group rules or cached auth snapshots.
func ApplyRateResolutionToUsageLog(log *UsageLog, resolution *RateResolution) {
	if log == nil || resolution == nil || resolution.PricingGroupID <= 0 {
		return
	}
	pricingGroupID := resolution.PricingGroupID
	rateMatchModel := resolution.MatchModel
	rateRuleSource := resolution.RateRuleSource
	rateRuleKey := resolution.RateRuleKey
	rateConfigVersion := resolution.RateConfigVersion
	rateBaseMultiplier := resolution.BaseMultiplier
	rateTokenMultiplier := resolution.TokenMultiplier
	rateImageMultiplier := resolution.ImageMultiplier
	rateVideoMultiplier := resolution.VideoMultiplier

	log.PricingGroupID = &pricingGroupID
	log.RateMatchModel = &rateMatchModel
	log.RateRuleSource = &rateRuleSource
	log.RateRuleKey = &rateRuleKey
	log.RateConfigVersion = &rateConfigVersion
	log.RateBaseMultiplier = &rateBaseMultiplier
	log.RateTokenMultiplier = &rateTokenMultiplier
	log.RateImageMultiplier = &rateImageMultiplier
	log.RateVideoMultiplier = &rateVideoMultiplier
}
