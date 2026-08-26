package service

import (
	"context"
	"fmt"
	"time"

	"github.com/Wei-Shaw/sub2api/internal/pkg/logger"
	gocache "github.com/patrickmn/go-cache"
	"golang.org/x/sync/singleflight"
)

// userGroupRateOverrideCacheValue caches the existence of a user override, not
// a final multiplier. Caching the final value would make changed group model
// rules or defaults keep charging stale prices for users without overrides.
type userGroupRateOverrideCacheValue struct {
	Exists     bool
	Multiplier float64
}

type userGroupRateResolver struct {
	repo         UserGroupRateRepository
	cache        *gocache.Cache
	cacheTTL     time.Duration
	sf           *singleflight.Group
	logComponent string
}

func newUserGroupRateResolver(repo UserGroupRateRepository, cache *gocache.Cache, cacheTTL time.Duration, sf *singleflight.Group, logComponent string) *userGroupRateResolver {
	if cacheTTL <= 0 {
		cacheTTL = defaultUserGroupRateCacheTTL
	}
	if cache == nil {
		cache = gocache.New(cacheTTL, time.Minute)
	}
	if logComponent == "" {
		logComponent = "service.gateway"
	}
	if sf == nil {
		sf = &singleflight.Group{}
	}
	return &userGroupRateResolver{repo: repo, cache: cache, cacheTTL: cacheTTL, sf: sf, logComponent: logComponent}
}

// ResolveOverride returns the user-group override when it exists. A repository
// failure is intentionally returned to the caller: new model-rate billing must
// never silently fall back to a different group rate on a failed lookup.
func (r *userGroupRateResolver) ResolveOverride(ctx context.Context, userID, groupID int64) (*float64, error) {
	if r == nil || userID <= 0 || groupID <= 0 || r.repo == nil {
		return nil, nil
	}
	key := fmt.Sprintf("%d:%d", userID, groupID)
	if value, ok := r.cachedOverride(key); ok {
		return overrideCacheValueToPointer(value), nil
	}
	userGroupRateCacheMissTotal.Add(1)
	value, err, shared := r.sf.Do(key, func() (any, error) {
		if cached, ok := r.cachedOverride(key); ok {
			userGroupRateCacheHitTotal.Add(1)
			return cached, nil
		}
		userGroupRateCacheLoadTotal.Add(1)
		userRate, repoErr := r.repo.GetByUserAndGroup(ctx, userID, groupID)
		if repoErr != nil {
			return nil, repoErr
		}
		cached := userGroupRateOverrideCacheValue{Exists: userRate != nil}
		if userRate != nil {
			cached.Multiplier = *userRate
		}
		if r.cache != nil {
			r.cache.Set(key, cached, r.cacheTTL)
		}
		return cached, nil
	})
	if shared {
		userGroupRateCacheSFSharedTotal.Add(1)
	}
	if err != nil {
		return nil, err
	}
	cached, ok := value.(userGroupRateOverrideCacheValue)
	if !ok {
		return nil, fmt.Errorf("invalid user group rate cache value")
	}
	return overrideCacheValueToPointer(cached), nil
}

func (r *userGroupRateResolver) cachedOverride(key string) (userGroupRateOverrideCacheValue, bool) {
	if r == nil || r.cache == nil {
		return userGroupRateOverrideCacheValue{}, false
	}
	cached, ok := r.cache.Get(key)
	if !ok {
		return userGroupRateOverrideCacheValue{}, false
	}
	value, castOK := cached.(userGroupRateOverrideCacheValue)
	if !castOK {
		return userGroupRateOverrideCacheValue{}, false
	}
	userGroupRateCacheHitTotal.Add(1)
	return value, true
}

func overrideCacheValueToPointer(value userGroupRateOverrideCacheValue) *float64 {
	if !value.Exists {
		return nil
	}
	multiplier := value.Multiplier
	return &multiplier
}

// Resolve preserves the legacy caller contract. New request-rate code must use
// ResolveOverride and propagate errors so it can fail closed rather than charge
// a fallback multiplier after a database failure.
func (r *userGroupRateResolver) Resolve(ctx context.Context, userID, groupID int64, groupDefaultMultiplier float64) float64 {
	override, err := r.ResolveOverride(ctx, userID, groupID)
	if err != nil {
		userGroupRateCacheFallbackTotal.Add(1)
		logger.LegacyPrintf(r.logComponent, "get user group rate failed, fallback to group default: user=%d group=%d err=%v", userID, groupID, err)
		return groupDefaultMultiplier
	}
	if override == nil {
		return groupDefaultMultiplier
	}
	return *override
}
