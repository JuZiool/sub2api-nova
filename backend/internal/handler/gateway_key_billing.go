package handler

import (
	"net/http"
	"time"

	"github.com/Wei-Shaw/sub2api/internal/config"
	"github.com/Wei-Shaw/sub2api/internal/pkg/timezone"
	middleware2 "github.com/Wei-Shaw/sub2api/internal/server/middleware"
	"github.com/Wei-Shaw/sub2api/internal/service"
	"github.com/gin-gonic/gin"
)

const keyBillingInfoSchemaVersion = 2

type keyBillingInfoResponse struct {
	Object                  string   `json:"object"`
	SchemaVersion           int      `json:"schema_version"`
	BillingScope            string   `json:"billing_scope"`
	GroupRateMultiplier     float64  `json:"group_rate_multiplier"`
	UserRateMultiplier      *float64 `json:"user_rate_multiplier,omitempty"`
	ResolvedRateMultiplier  float64  `json:"resolved_rate_multiplier"`
	PeakRateEnabled         bool     `json:"peak_rate_enabled"`
	PeakStart               *string  `json:"peak_start,omitempty"`
	PeakEnd                 *string  `json:"peak_end,omitempty"`
	PeakRateMultiplier      *float64 `json:"peak_rate_multiplier,omitempty"`
	AppliedPeakMultiplier   *float64 `json:"applied_peak_multiplier,omitempty"`
	EffectiveRateMultiplier float64  `json:"effective_rate_multiplier"`
	Timezone                *string  `json:"timezone,omitempty"`
	// The following fields are returned only for GET /v1/sub2api/billing?model=... .
	// The no-query response keeps its legacy group-level semantics.
	RequestedModel      *string   `json:"requested_model,omitempty"`
	RateMatchModel      *string   `json:"rate_match_model,omitempty"`
	RateRuleSource      *string   `json:"rate_rule_source,omitempty"`
	RateRuleKey         *string   `json:"rate_rule_key,omitempty"`
	RateConfigVersion   *int64    `json:"rate_config_version,omitempty"`
	RateBaseMultiplier  *float64  `json:"rate_base_multiplier,omitempty"`
	RateTokenMultiplier *float64  `json:"rate_token_multiplier,omitempty"`
	RateImageMultiplier *float64  `json:"rate_image_multiplier,omitempty"`
	RateVideoMultiplier *float64  `json:"rate_video_multiplier,omitempty"`
	ObservedAt          time.Time `json:"observed_at"`
}

// KeyBillingInfo returns the token billing multiplier effective for the authenticated API key.
// GET /v1/sub2api/billing
func (h *GatewayHandler) KeyBillingInfo(c *gin.Context) {
	apiKey, ok := middleware2.GetAPIKeyFromContext(c)
	if !ok {
		h.errorResponse(c, http.StatusUnauthorized, "authentication_error", "Invalid API key")
		return
	}
	if h.cfg != nil && h.cfg.RunMode == config.RunModeSimple {
		h.errorResponse(c, http.StatusNotFound, "not_found_error", "Billing information is not supported in simple mode")
		return
	}
	if apiKey.GroupID == nil {
		h.errorResponse(c, http.StatusForbidden, "permission_error", "API key is not assigned to a group")
		return
	}
	if apiKey.Group == nil {
		h.errorResponse(c, http.StatusInternalServerError, "api_error", "Billing information is unavailable")
		return
	}

	now := timezone.Now()
	model := c.Query("model")
	if model != "" {
		resolution, ok := h.resolveKeyBillingRateResolution(c, apiKey, model, now)
		if !ok {
			h.errorResponse(c, http.StatusInternalServerError, "api_error", "Billing information is unavailable")
			return
		}
		c.Header("Cache-Control", "no-store")
		c.JSON(http.StatusOK, buildKeyBillingInfoForModel(apiKey, resolution, now))
		return
	}

	resolvedRate, ok := h.resolveKeyBillingRate(c, apiKey)
	if !ok {
		h.errorResponse(c, http.StatusInternalServerError, "api_error", "Billing information is unavailable")
		return
	}

	c.Header("Cache-Control", "no-store")
	c.JSON(http.StatusOK, buildKeyBillingInfo(apiKey, resolvedRate, now))
}

func (h *GatewayHandler) resolveKeyBillingRate(c *gin.Context, apiKey *service.APIKey) (float64, bool) {
	groupRate := apiKey.Group.RateMultiplier
	switch apiKey.Group.Platform {
	case service.PlatformOpenAI, service.PlatformGrok:
		if h.openAIGatewayService == nil {
			return 0, false
		}
		return h.openAIGatewayService.ResolveUserGroupRateMultiplier(c.Request.Context(), apiKey.UserID, *apiKey.GroupID, groupRate), true
	default:
		if h.gatewayService == nil {
			return 0, false
		}
		return h.gatewayService.ResolveUserGroupRateMultiplier(c.Request.Context(), apiKey.UserID, *apiKey.GroupID, groupRate), true
	}
}

func (h *GatewayHandler) resolveKeyBillingRateResolution(c *gin.Context, apiKey *service.APIKey, model string, now time.Time) (*service.RateResolution, bool) {
	if apiKey == nil || apiKey.GroupID == nil || apiKey.Group == nil {
		return nil, false
	}
	var (
		resolution *service.RateResolution
		err        error
	)
	switch apiKey.Group.Platform {
	case service.PlatformOpenAI, service.PlatformGrok:
		if h.openAIGatewayService == nil {
			return nil, false
		}
		resolution, err = h.openAIGatewayService.ResolveRequestRateResolution(c.Request.Context(), apiKey.UserID, apiKey.Group, model, now)
	default:
		if h.gatewayService == nil {
			return nil, false
		}
		resolution, err = h.gatewayService.ResolveRequestRateResolution(c.Request.Context(), apiKey.UserID, apiKey.Group, model, now)
	}
	return resolution, err == nil && resolution != nil
}

func buildKeyBillingInfoForModel(apiKey *service.APIKey, resolution *service.RateResolution, now time.Time) keyBillingInfoResponse {
	response := buildKeyBillingInfo(apiKey, resolution.BaseMultiplier, now)
	requestedModel := resolution.RequestedModel
	rateMatchModel := resolution.MatchModel
	rateRuleSource := resolution.RateRuleSource
	rateRuleKey := resolution.RateRuleKey
	rateConfigVersion := resolution.RateConfigVersion
	rateBaseMultiplier := resolution.BaseMultiplier
	rateTokenMultiplier := resolution.TokenMultiplier
	rateImageMultiplier := resolution.ImageMultiplier
	rateVideoMultiplier := resolution.VideoMultiplier
	response.RequestedModel = &requestedModel
	response.RateMatchModel = &rateMatchModel
	response.RateRuleSource = &rateRuleSource
	response.RateRuleKey = &rateRuleKey
	response.RateConfigVersion = &rateConfigVersion
	response.RateBaseMultiplier = &rateBaseMultiplier
	response.RateTokenMultiplier = &rateTokenMultiplier
	response.RateImageMultiplier = &rateImageMultiplier
	response.RateVideoMultiplier = &rateVideoMultiplier
	response.ResolvedRateMultiplier = resolution.BaseMultiplier
	response.EffectiveRateMultiplier = resolution.TokenMultiplier
	// In model-preview mode this field must retain its literal meaning. A model
	// rule is not a user-specific override.
	if resolution.RateRuleSource != "user_group_override" {
		response.UserRateMultiplier = nil
	}
	return response
}

func buildKeyBillingInfo(apiKey *service.APIKey, resolvedRate float64, now time.Time) keyBillingInfoResponse {
	groupRate := apiKey.Group.RateMultiplier
	var userRate *float64
	if resolvedRate != groupRate {
		userRate = &resolvedRate
	}
	appliedPeak := apiKey.Group.PeakMultiplierAt(now)

	response := keyBillingInfoResponse{
		Object:                  "sub2api.key_billing",
		SchemaVersion:           keyBillingInfoSchemaVersion,
		BillingScope:            "token",
		GroupRateMultiplier:     groupRate,
		UserRateMultiplier:      userRate,
		ResolvedRateMultiplier:  resolvedRate,
		PeakRateEnabled:         apiKey.Group.PeakRateEnabled,
		EffectiveRateMultiplier: resolvedRate * appliedPeak,
		ObservedAt:              now.UTC(),
	}
	if apiKey.Group.PeakRateEnabled {
		response.PeakStart = &apiKey.Group.PeakStart
		response.PeakEnd = &apiKey.Group.PeakEnd
		response.PeakRateMultiplier = &apiKey.Group.PeakRateMultiplier
		response.AppliedPeakMultiplier = &appliedPeak
		tz := timezone.Location().String()
		response.Timezone = &tz
	}
	return response
}
